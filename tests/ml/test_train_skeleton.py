"""Tests for training skeleton."""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
import yaml
from torch.utils.data import DataLoader
from torch.amp import GradScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.training.train import train_one_epoch, evaluate, main
from ml_pipeline.training.metrics import ContinuousMetrics, BinaryMetrics
from ml_pipeline.models.network import MultimodalStressNet
from ml_pipeline.training.losses import ProxyRegressionLoss
from ml_pipeline.data.dataset import AgMultidaDataset
from ml_pipeline.data.sample import AlignedSample
from tests.data_contract.conftest import make_valid_sample_kwargs


def _make_dummy_dataloader(batch_size=2):
    return [
        {
            "image": torch.randn(batch_size, 4, 224, 224),
            "sensor_seq": torch.randn(batch_size, 48, 8),
            "weather_ctx": torch.randn(batch_size, 6),
            "modality_mask": torch.ones(batch_size, 3),
            "label": torch.rand(batch_size, 1),
        }
    ]


def _write_manifest_dataset(root: Path) -> None:
    for sample_id in ["A01_20240101_TEST1234", "D01_20240102_TEST5678", "E01_20240103_TEST9012"]:
        sample_dir = root / "samples" / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        np.save(sample_dir / "image.npy", np.ones((4, 224, 224), dtype=np.float32))
        np.save(sample_dir / "sensor_seq.npy", np.ones((48, 8), dtype=np.float32))
        np.save(sample_dir / "weather_ctx.npy", np.ones((6,), dtype=np.float32))
    rows = [
        {"sample_id": "A01_20240101_TEST1234", "zone_id": "A01", "image_path": "samples/A01_20240101_TEST1234/image.npy", "sensor_seq_path": "samples/A01_20240101_TEST1234/sensor_seq.npy", "weather_ctx_path": "samples/A01_20240101_TEST1234/weather_ctx.npy", "modality_mask": "[1.0, 1.0, 1.0]", "label": 0.2, "source_status": "PASS", "checksum": ""},
        {"sample_id": "D01_20240102_TEST5678", "zone_id": "D01", "image_path": "samples/D01_20240102_TEST5678/image.npy", "sensor_seq_path": "samples/D01_20240102_TEST5678/sensor_seq.npy", "weather_ctx_path": "samples/D01_20240102_TEST5678/weather_ctx.npy", "modality_mask": "[1.0, 1.0, 1.0]", "label": 0.6, "source_status": "PASS", "checksum": ""},
        {"sample_id": "E01_20240103_TEST9012", "zone_id": "E01", "image_path": "samples/E01_20240103_TEST9012/image.npy", "sensor_seq_path": "samples/E01_20240103_TEST9012/sensor_seq.npy", "weather_ctx_path": "samples/E01_20240103_TEST9012/weather_ctx.npy", "modality_mask": "[1.0, 1.0, 1.0]", "label": 0.8, "source_status": "PASS", "checksum": ""},
    ]
    pd.DataFrame([rows[0]]).to_csv(root / "train_manifest.csv", index=False)
    pd.DataFrame([rows[1]]).to_csv(root / "val_manifest.csv", index=False)
    pd.DataFrame([rows[2]]).to_csv(root / "test_manifest.csv", index=False)


class TestTrainSkeleton:
    def test_train_one_epoch_runs(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = ProxyRegressionLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)

        metrics = train_one_epoch(model, dataloader, loss_fn, optimizer, None, scaler, torch.device("cpu"))
        assert "loss" in metrics
        assert isinstance(metrics["loss"], float)

    def test_evaluate_returns_continuous_metrics(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        results = evaluate(
            model=model,
            dataloader=dataloader,
            loss_fn=ProxyRegressionLoss(),
            metrics=ContinuousMetrics(),
            binary_metrics=BinaryMetrics(),
            device=torch.device("cpu"),
        )
        assert "loss" in results
        assert "mae" in results
        assert "rmse" in results
        assert "binary_f1" in results

    def test_config_loading(self):
        config_path = Path(__file__).resolve().parent.parent.parent / "ml_pipeline" / "configs" / "train.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert config["training"]["data_dir"] == "data/processed_real/"
        assert config["training"]["checkpoint_metric"] == "rmse"

    def test_train_with_dataset(self):
        samples = [AlignedSample(**make_valid_sample_kwargs(seed=i)) for i in range(2)]
        dataset = AgMultidaDataset(samples)
        dataloader = DataLoader(dataset, batch_size=2)
        model = MultimodalStressNet(pretrained_backbone=False)
        metrics = train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=ProxyRegressionLoss(),
            optimizer=torch.optim.AdamW(model.parameters(), lr=1e-3),
            scheduler=None,
            scaler=GradScaler(enabled=False),
            device=torch.device("cpu"),
        )
        assert metrics["loss"] > 0

    def test_train_updates_parameters(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = ProxyRegressionLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)
        params_before = [p.clone() for p in model.parameters()]
        train_one_epoch(model, dataloader, loss_fn, optimizer, None, scaler, torch.device("cpu"))
        for p_before, p_after in zip(params_before, model.parameters()):
            if not torch.allclose(p_before, p_after):
                break
        else:
            pytest.fail("Model parameters did not change after training step.")

    def test_main_dry_run_creates_checkpoints(self):
        config_dir = Path(__file__).resolve().parent.parent.parent / "ml_pipeline" / "configs"
        with tempfile.TemporaryDirectory() as tmpdir:
            import unittest.mock as mock
            from ml_pipeline.training import train
            orig_load_yaml = train.load_yaml

            def fake_load_yaml(path):
                cfg = orig_load_yaml(path)
                if "training" in cfg:
                    cfg["training"]["checkpoint_dir"] = tmpdir
                    cfg["training"]["evaluate_test_manifest"] = False
                return cfg

            with mock.patch("ml_pipeline.training.train.load_yaml", side_effect=fake_load_yaml):
                train.main(config_dir, dry_run=True)
            assert (Path(tmpdir) / "latest.pt").exists()
            assert (Path(tmpdir) / "best.pt").exists()

    def test_main_non_dry_run_uses_manifests_and_writes_test_metrics(self):
        config_dir = Path(__file__).resolve().parent.parent.parent / "ml_pipeline" / "configs"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_dir = root / "dataset"
            data_dir.mkdir(parents=True, exist_ok=True)
            _write_manifest_dataset(data_dir)
            ckpt_dir = root / "ckpt"
            log_dir = root / "logs"
            main(
                config_dir=config_dir,
                data_dir=data_dir,
                checkpoint_dir=ckpt_dir,
                log_dir=log_dir,
                max_epochs=1,
                num_workers=0,
            )
            assert (ckpt_dir / "latest.pt").exists()
            assert (ckpt_dir / "best.pt").exists()
            log_text = (log_dir / "training_metrics.csv").read_text(encoding="utf-8")
            assert "test_rmse" in log_text
