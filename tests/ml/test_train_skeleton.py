"""Tests for training skeleton.

Run: pytest tests/ml/test_train_skeleton.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch
import yaml
from torch.utils.data import DataLoader, TensorDataset
from torch.amp import GradScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.training.train import train_one_epoch, evaluate
from ml_pipeline.training.metrics import BinaryMetrics
from ml_pipeline.models.network import MultimodalStressNet
from ml_pipeline.training.losses import SmoothedBCEWithLogitsLoss
from ml_pipeline.data.dataset import AgMultidaDataset
from ml_pipeline.data.sample import AlignedSample
from tests.data_contract.conftest import make_valid_sample_kwargs


def _make_dummy_dataloader(batch_size=2):
    """Creates a mock dataloader matching the dataset dict format."""
    return [
        {
            "image": torch.randn(batch_size, 4, 224, 224),
            "sensor_seq": torch.randn(batch_size, 48, 8),
            "weather_ctx": torch.randn(batch_size, 6),
            "modality_mask": torch.ones(batch_size, 3),
            "label": torch.rand(batch_size, 1),
        }
    ]


class TestTrainSkeleton:
    def test_train_one_epoch_runs(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = SmoothedBCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)
        
        device = torch.device("cpu")
        
        metrics = train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=None,
            scaler=scaler,
            device=device,
        )
        assert "loss" in metrics
        assert isinstance(metrics["loss"], float)

    def test_train_one_epoch_loss_finite(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = SmoothedBCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)
        
        metrics = train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=None,
            scaler=scaler,
            device=torch.device("cpu"),
        )
        assert metrics["loss"] > 0
        import math
        assert not math.isnan(metrics["loss"])
        assert not math.isinf(metrics["loss"])

    def test_evaluate_returns_metrics(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = SmoothedBCEWithLogitsLoss()
        metrics_obj = BinaryMetrics()
        
        results = evaluate(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            metrics=metrics_obj,
            device=torch.device("cpu"),
        )
        assert "loss" in results
        assert "accuracy" in results
        assert "f1" in results

    def test_scheduler_step_no_error(self):
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = SmoothedBCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1)
        scaler = GradScaler(enabled=False)
        
        lr_before = optimizer.param_groups[0]["lr"]
        
        train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            device=torch.device("cpu"),
        )
        
        lr_after = optimizer.param_groups[0]["lr"]
        assert lr_before != lr_after

    def test_amp_scaler_cpu_safe(self):
        # Even with CPU, if scaler.enabled=False, it should not crash
        model = MultimodalStressNet(pretrained_backbone=False)
        dataloader = _make_dummy_dataloader(batch_size=2)
        loss_fn = SmoothedBCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)
        
        train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=None,
            scaler=scaler,
            device=torch.device("cpu"),
        )
        # implicitly passes if no exception

    def test_config_loading(self):
        config_path = Path(__file__).resolve().parent.parent.parent / "ml_pipeline" / "configs" / "train.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "training" in config
        assert "data_dir" in config["training"]
        assert "dry_run" in config["training"]

    def test_train_with_dataset(self):
        """Train step using the actual AgMultidaDataset."""
        samples = [AlignedSample(**make_valid_sample_kwargs(seed=i)) for i in range(2)]
        dataset = AgMultidaDataset(samples)
        dataloader = DataLoader(dataset, batch_size=2)
        
        model = MultimodalStressNet(pretrained_backbone=False)
        loss_fn = SmoothedBCEWithLogitsLoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = GradScaler(enabled=False)
        
        metrics = train_one_epoch(
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            scheduler=None,
            scaler=scaler,
            device=torch.device("cpu"),
        )
        assert metrics["loss"] > 0
