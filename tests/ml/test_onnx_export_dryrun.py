"""ONNX export dry-run test: export dummy model and verify output shapes.

Validates that MultimodalStressNet can be exported to ONNX and reloaded
with correct I/O shapes matching onnx_io_contract.yaml.
Run: pytest tests/ml/test_onnx_export_dryrun.py -v
"""
from __future__ import annotations

import pytest


class TestOnnxExportDryRun:
    def test_dry_run_passes(self):
        """Full dry-run: export -> reload -> verify shapes."""
        from ml_pipeline.export.export_onnx import dry_run
        assert dry_run() is True

    def test_dummy_inputs_correct_shapes(self):
        from ml_pipeline.export.export_onnx import make_dummy_inputs
        dummy = make_dummy_inputs(batch_size=1)
        assert dummy["image"].shape == (1, 4, 224, 224)
        assert dummy["sensor_seq"].shape == (1, 48, 8)
        assert dummy["weather_ctx"].shape == (1, 6)
        assert dummy["modality_mask"].shape == (1, 3)

    def test_export_creates_valid_file(self):
        import tempfile
        from pathlib import Path
        import torch
        from ml_pipeline.models.network import MultimodalStressNet
        from ml_pipeline.export.export_onnx import export_onnx

        model = MultimodalStressNet(pretrained_backbone=False)
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            path = f.name
        try:
            export_onnx(model, path)
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0
        finally:
            Path(path).unlink(missing_ok=True)
