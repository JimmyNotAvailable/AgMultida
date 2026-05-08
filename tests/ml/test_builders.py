"""Tests for config builders and manifest dataset loading."""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.training.builders import (
    ManifestDataset,
    load_yaml,
    resolve_device,
    build_model,
    build_loss,
    build_optimizer,
    build_scheduler,
    build_scaler,
)


@pytest.fixture
def mock_config():
    return {
        "model": {"name": "test", "version": "1.0.0"},
        "image_encoder": {"pretrained": "imagenet"},
        "fusion": {"d_model": 256, "num_heads": 4, "dropout": 0.1},
        "temporal_encoder": {"input_dim": 8, "hidden_dim": 128, "num_layers": 2, "dropout": 0.3},
        "weather_encoder": {"input_dim": 6, "hidden_dim": 64},
        "regularization": {"modality_dropout": 0.3, "label_smoothing": 0.1},
        "training": {
            "loss": "proxy_mse",
            "optimizer": "adamw",
            "lr": 3e-4,
            "weight_decay": 1e-4,
            "scheduler": "one_cycle_lr",
            "max_epochs": 10,
            "amp": True,
        }
    }


def _write_valid_manifest(root: Path) -> Path:
    sample_dir = root / "samples" / "A01_20240101_TEST1234"
    sample_dir.mkdir(parents=True, exist_ok=True)
    image_path = sample_dir / "image.npy"
    sensor_path = sample_dir / "sensor_seq.npy"
    weather_path = sample_dir / "weather_ctx.npy"
    np.save(image_path, np.ones((4, 224, 224), dtype=np.float32))
    np.save(sensor_path, np.ones((48, 8), dtype=np.float32))
    np.save(weather_path, np.ones((6,), dtype=np.float32))
    df = pd.DataFrame([
        {
            "sample_id": "A01_20240101_TEST1234",
            "zone_id": "A01",
            "image_path": "samples/A01_20240101_TEST1234/image.npy",
            "sensor_seq_path": "samples/A01_20240101_TEST1234/sensor_seq.npy",
            "weather_ctx_path": "samples/A01_20240101_TEST1234/weather_ctx.npy",
            "modality_mask": "[1.0, 1.0, 1.0]",
            "label": 0.42,
            "source_status": "PASS",
            "checksum": "",
        }
    ])
    manifest = root / "train_manifest.csv"
    df.to_csv(manifest, index=False)
    return manifest


class TestBuilders:
    def test_load_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("foo: bar\n")
            path = f.name

        try:
            cfg = load_yaml(path)
            assert cfg["foo"] == "bar"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_resolve_device(self):
        assert resolve_device("cpu").type == "cpu"
        if torch.cuda.is_available():
            assert resolve_device("cuda").type == "cuda"
            assert resolve_device("auto").type == "cuda"
        else:
            assert resolve_device("auto").type == "cpu"

    def test_build_model(self, mock_config):
        import unittest.mock as mock
        with mock.patch("ml_pipeline.models.image_encoder.timm.create_model") as mock_timm:
            mock_backbone = mock.MagicMock()
            mock_backbone.num_features = 1536
            mock_backbone.conv_stem = torch.nn.Conv2d(3, 32, 3)
            mock_timm.return_value = mock_backbone

            model = build_model(mock_config, pretrained=False)
            assert model.cross_attention.cross_attn.embed_dim == 256

    def test_build_model_uses_pretrained_flag_from_config(self, mock_config):
        import unittest.mock as mock
        with mock.patch("ml_pipeline.models.image_encoder.timm.create_model") as mock_timm:
            mock_backbone = mock.MagicMock()
            mock_backbone.num_features = 1536
            mock_backbone.conv_stem = torch.nn.Conv2d(3, 32, 3)
            mock_timm.return_value = mock_backbone

            model = build_model(mock_config, pretrained=False)
            assert model.image_encoder is not None
            assert mock_timm.call_args.kwargs["pretrained"] is False

    def test_build_loss(self, mock_config):
        loss = build_loss(mock_config)
        assert loss.smoothing == 0.1

    def test_build_optimizer(self, mock_config):
        model = torch.nn.Linear(10, 2)
        opt = build_optimizer(model, mock_config)
        assert isinstance(opt, torch.optim.AdamW)
        assert opt.defaults["lr"] == 3e-4

    def test_build_scheduler(self, mock_config):
        model = torch.nn.Linear(10, 2)
        opt = build_optimizer(model, mock_config)
        sched = build_scheduler(opt, mock_config, steps_per_epoch=100)
        assert isinstance(sched, torch.optim.lr_scheduler.OneCycleLR)
        assert sched.total_steps == 1000

    def test_build_scaler(self):
        cpu_scaler = build_scaler(torch.device("cpu"), True)
        assert not cpu_scaler.is_enabled()

        if torch.cuda.is_available():
            cuda_scaler = build_scaler(torch.device("cuda"), True)
            assert cuda_scaler.is_enabled()

    def test_manifest_dataset_loads_valid_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = _write_valid_manifest(Path(tmpdir))
            dataset = ManifestDataset(manifest)
            sample = dataset[0]
            assert tuple(sample["image"].shape) == (4, 224, 224)
            assert tuple(sample["sensor_seq"].shape) == (48, 8)
            assert tuple(sample["weather_ctx"].shape) == (6,)
            assert tuple(sample["label"].shape) == (1,)

    def test_manifest_dataset_rejects_missing_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = _write_valid_manifest(root)
            frame = pd.read_csv(manifest)
            frame = frame.drop(columns=["label"])
            frame.to_csv(manifest, index=False)
            with pytest.raises(ValueError, match="missing required columns"):
                ManifestDataset(manifest)

    def test_manifest_dataset_rejects_bad_source_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = _write_valid_manifest(root)
            frame = pd.read_csv(manifest)
            frame.loc[0, "source_status"] = "FAIL"
            frame.to_csv(manifest, index=False)
            with pytest.raises(ValueError, match="source_status"):
                ManifestDataset(manifest)

    def test_manifest_dataset_rejects_bad_mask(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = _write_valid_manifest(root)
            frame = pd.read_csv(manifest)
            frame.loc[0, "modality_mask"] = "[1.0, 0.5, 0.0]"
            frame.to_csv(manifest, index=False)
            with pytest.raises(ValueError, match="modality_mask"):
                ManifestDataset(manifest)

    def test_manifest_dataset_rejects_bad_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = _write_valid_manifest(root)
            bad_path = root / "samples" / "A01_20240101_TEST1234" / "image.npy"
            np.save(bad_path, np.ones((3, 224, 224), dtype=np.float32))
            with pytest.raises(ValueError, match="shape"):
                ManifestDataset(manifest)
