"""Tests for checkpoint save/load roundtrip.

Run: pytest tests/ml/test_checkpoint.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile

import pytest
import torch
import torch.nn as nn
from torch.optim import AdamW

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.training.train import save_checkpoint, load_checkpoint
from ml_pipeline.models.network import MultimodalStressNet


class TestCheckpoint:
    def test_save_load_roundtrip(self):
        model1 = MultimodalStressNet(pretrained_backbone=False)
        optimizer1 = AdamW(model1.parameters(), lr=1e-3)
        metrics = {"loss": 0.42, "accuracy": 0.9}

        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path = Path(tmpdir) / "model.pt"
            save_checkpoint(ckpt_path, model1, optimizer1, None, epoch=1, metrics=metrics)

            # Create new model
            model2 = MultimodalStressNet(pretrained_backbone=False)
            
            # Verify weights differ initially (due to random init)
            for p1, p2 in zip(model1.parameters(), model2.parameters()):
                if not torch.allclose(p1, p2):
                    break
            else:
                pytest.fail("Models identical before load (bad test setup)")

            # Load checkpoint
            metadata = load_checkpoint(ckpt_path, model2)

            # Verify weights are identical after load
            for p1, p2 in zip(model1.parameters(), model2.parameters()):
                assert torch.allclose(p1, p2)

            assert metadata["epoch"] == 1
            assert metadata["metrics"]["loss"] == 0.42

    def test_checkpoint_contains_metadata(self):
        model = nn.Linear(10, 1)
        optimizer = AdamW(model.parameters(), lr=1e-3)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path = Path(tmpdir) / "model.pt"
            save_checkpoint(ckpt_path, model, optimizer, None, epoch=5, metrics={}, config={"foo": "bar"})
            
            state = torch.load(ckpt_path, weights_only=True)
            assert "epoch" in state
            assert "metrics" in state
            assert "config" in state
            assert state["config"]["foo"] == "bar"

    def test_load_missing_file_raises(self):
        model = nn.Linear(10, 1)
        with pytest.raises(FileNotFoundError):
            load_checkpoint("non_existent_path.pt", model)

    def test_checkpoint_optimizer_state(self):
        model = nn.Linear(10, 1)
        optimizer1 = AdamW(model.parameters(), lr=1e-3)
        
        # Take a step to change optimizer state
        loss = model(torch.randn(2, 10)).sum()
        loss.backward()
        optimizer1.step()

        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path = Path(tmpdir) / "model.pt"
            save_checkpoint(ckpt_path, model, optimizer1, None, epoch=1, metrics={})

            optimizer2 = AdamW(model.parameters(), lr=1e-3)
            load_checkpoint(ckpt_path, model, optimizer=optimizer2)
            
            # Check optimizer states match (simplistic check)
            assert str(optimizer1.state_dict()) == str(optimizer2.state_dict())
