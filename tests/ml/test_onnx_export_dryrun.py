"""ONNX export dry-run and checkpoint loading tests.

Validates export metadata, multi-batch verification, and checkpoint wrapper
compatibility for MultimodalStressNet ONNX export flow.
Run: pytest tests/ml/test_onnx_export_dryrun.py -v
"""
from __future__ import annotations

import pickle
from unittest.mock import patch

import pytest
import torch
from torch.optim import AdamW

from ml_pipeline.export.export_onnx import (
    EXPECTED_OUTPUT_DIMENSIONS,
    INPUT_SPECS,
    OUTPUT_NAMES,
    dry_run,
    export_onnx,
    load_model_checkpoint,
    make_dummy_inputs,
    verify_onnx,
)
from ml_pipeline.models.network import MultimodalStressNet
from ml_pipeline.training.train import save_checkpoint


class TestOnnxExportDryRun:
    def test_dry_run_passes(self):
        result = dry_run()
        assert result["all_checks_passed"] is True
        assert result["verified_batch_sizes"] == [1, 2, 4]
        assert result["model_size_mb"] > 0
        assert result["latency_ms"] >= 0

    @pytest.mark.parametrize("batch_size", [1, 2, 4])
    def test_dummy_inputs_correct_shapes(self, batch_size):
        dummy = make_dummy_inputs(batch_size=batch_size)
        assert dummy["image"].shape == (batch_size, 4, 224, 224)
        assert dummy["sensor_seq"].shape == (batch_size, 48, 8)
        assert dummy["weather_ctx"].shape == (batch_size, 6)
        assert dummy["modality_mask"].shape == (batch_size, 3)

    def test_export_creates_valid_file(self, tmp_path):
        model = MultimodalStressNet(pretrained_backbone=False)
        path = tmp_path / "model.onnx"

        report = export_onnx(model, str(path))

        assert path.exists()
        assert path.stat().st_size > 0
        assert report["output_path"] == str(path)
        assert report["model_size_mb"] > 0

    def test_export_retries_without_dynamo_for_older_torch(self, tmp_path):
        model = MultimodalStressNet(pretrained_backbone=False)
        path = tmp_path / "model.onnx"
        real_export = torch.onnx.export
        calls = []

        def fake_export(*args, **kwargs):
            calls.append(kwargs.copy())
            if len(calls) == 1 and "dynamo" in kwargs:
                raise TypeError("export() got an unexpected keyword argument 'dynamo'")
            return real_export(*args, **kwargs)

        with patch("ml_pipeline.export.export_onnx.torch.onnx.export", side_effect=fake_export):
            report = export_onnx(model, str(path))

        assert path.exists()
        assert report["model_size_mb"] > 0
        assert calls[0]["dynamo"] is False
        assert "dynamo" not in calls[1]

    def test_verify_onnx_reports_names_shapes_and_batches(self, tmp_path):
        model = MultimodalStressNet(pretrained_backbone=False)
        path = tmp_path / "verify.onnx"
        export_onnx(model, str(path))

        report = verify_onnx(str(path), batch_sizes=(1, 2, 4))

        assert report["all_checks_passed"] is True
        assert report["input_names"] == list(INPUT_SPECS.keys())
        assert report["output_names"] == OUTPUT_NAMES
        assert report["verified_batch_sizes"] == [1, 2, 4]
        for batch_report in report["batch_reports"]:
            batch_size = batch_report["batch_size"]
            assert batch_report["passed"] is True
            for output_name, dims in EXPECTED_OUTPUT_DIMENSIONS.items():
                expected_shape = tuple(batch_size if dim == "B" else dim for dim in dims)
                assert tuple(batch_report["actual_output_shapes"][output_name]) == expected_shape

    def test_load_model_checkpoint_reads_model_state_dict_wrapper(self, tmp_path):
        source_model = MultimodalStressNet(pretrained_backbone=False)
        optimizer = AdamW(source_model.parameters(), lr=1e-3)
        checkpoint_path = tmp_path / "wrapped_checkpoint.pt"
        save_checkpoint(checkpoint_path, source_model, optimizer, None, epoch=3, metrics={"loss": 0.1})

        loaded_model = MultimodalStressNet(pretrained_backbone=False)
        metadata = load_model_checkpoint(loaded_model, str(checkpoint_path))

        for source_param, loaded_param in zip(source_model.parameters(), loaded_model.parameters()):
            assert torch.allclose(source_param, loaded_param)
        assert metadata["epoch"] == 3
        assert metadata["metrics"] == {"loss": 0.1}

    def test_load_model_checkpoint_supports_plain_state_dict(self, tmp_path):
        source_model = MultimodalStressNet(pretrained_backbone=False)
        checkpoint_path = tmp_path / "plain_state_dict.pt"
        torch.save(source_model.state_dict(), checkpoint_path)

        loaded_model = MultimodalStressNet(pretrained_backbone=False)
        metadata = load_model_checkpoint(loaded_model, str(checkpoint_path))

        for source_param, loaded_param in zip(source_model.parameters(), loaded_model.parameters()):
            assert torch.allclose(source_param, loaded_param)
        assert metadata["epoch"] is None
        assert metadata["metrics"] == {}

    def test_load_model_checkpoint_rejects_missing_model_weights(self, tmp_path):
        checkpoint_path = tmp_path / "invalid_checkpoint.pt"
        torch.save({"epoch": 1}, checkpoint_path)
        model = MultimodalStressNet(pretrained_backbone=False)

        with pytest.raises(KeyError, match="model_state_dict"):
            load_model_checkpoint(model, str(checkpoint_path))

    def test_load_model_checkpoint_raises_when_weights_only_fails_without_opt_in(self, tmp_path):
        source_model = MultimodalStressNet(pretrained_backbone=False)
        optimizer = AdamW(source_model.parameters(), lr=1e-3)
        checkpoint_path = tmp_path / "wrapped_checkpoint.pt"
        save_checkpoint(checkpoint_path, source_model, optimizer, None, epoch=5, metrics={"loss": 0.2})

        real_torch_load = torch.load

        def fake_torch_load(*args, **kwargs):
            if kwargs.get("weights_only") is True:
                raise pickle.UnpicklingError("weights only load failed")
            return real_torch_load(*args, **kwargs)

        loaded_model = MultimodalStressNet(pretrained_backbone=False)
        with patch("ml_pipeline.export.export_onnx.torch.load", side_effect=fake_torch_load):
            with pytest.raises(pickle.UnpicklingError, match="weights only load failed"):
                load_model_checkpoint(loaded_model, str(checkpoint_path))

    def test_load_model_checkpoint_falls_back_with_explicit_opt_in(self, tmp_path):
        source_model = MultimodalStressNet(pretrained_backbone=False)
        optimizer = AdamW(source_model.parameters(), lr=1e-3)
        checkpoint_path = tmp_path / "wrapped_checkpoint.pt"
        save_checkpoint(checkpoint_path, source_model, optimizer, None, epoch=5, metrics={"loss": 0.2})

        observed_weights_only = []
        real_torch_load = torch.load

        def fake_torch_load(*args, **kwargs):
            observed_weights_only.append(kwargs.get("weights_only"))
            if kwargs.get("weights_only") is True:
                raise pickle.UnpicklingError("weights only load failed")
            return real_torch_load(*args, **kwargs)

        loaded_model = MultimodalStressNet(pretrained_backbone=False)
        with patch("ml_pipeline.export.export_onnx.torch.load", side_effect=fake_torch_load):
            metadata = load_model_checkpoint(
                loaded_model,
                str(checkpoint_path),
                allow_unsafe_checkpoint_load=True,
            )

        assert observed_weights_only == [True, False]
        assert metadata["epoch"] == 5
        assert metadata["metrics"] == {"loss": 0.2}
        for source_param, loaded_param in zip(source_model.parameters(), loaded_model.parameters()):
            assert torch.allclose(source_param, loaded_param)
