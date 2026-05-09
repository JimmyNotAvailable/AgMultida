"""Smoke test: one training step (forward + loss + backward + optimizer step).

Validates that the full training loop works without shape/device errors.
Uses ProxyRegressionLoss with optional smoothing.
Run: pytest tests/ml/test_loss_one_step.py -v
"""
from __future__ import annotations

import torch
import pytest


def _make_dummy_batch(batch_size: int = 4):
    return (
        {
            "image": torch.randn(batch_size, 4, 224, 224),
            "sensor_seq": torch.randn(batch_size, 48, 8),
            "weather_ctx": torch.randn(batch_size, 6),
            "modality_mask": torch.ones(batch_size, 3),
        },
        torch.rand(batch_size, 1),  # labels in [0, 1]
    )


class TestOneTrainingStep:
    def test_loss_backward_completes(self):
        from ml_pipeline.models.network import MultimodalStressNet
        from ml_pipeline.training.losses import ProxyRegressionLoss

        model = MultimodalStressNet(pretrained_backbone=False)
        model.train()
        loss_fn = ProxyRegressionLoss(smoothing=0.1)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

        inputs, labels = _make_dummy_batch(batch_size=4)
        logits, _ = model(**inputs)
        loss = loss_fn(logits, labels)

        assert loss.requires_grad
        assert not torch.isnan(loss), "Loss is NaN"
        assert not torch.isinf(loss), "Loss is Inf"

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    def test_loss_value_range(self):
        from ml_pipeline.training.losses import ProxyRegressionLoss

        loss_fn = ProxyRegressionLoss(smoothing=0.1)
        logits = torch.randn(8, 1)
        labels = torch.rand(8, 1)
        loss = loss_fn(logits, labels)

        assert loss.item() >= 0.0, "Proxy regression loss must be non-negative"

    def test_label_smoothing_effect(self):
        """Smoothed labels should be pulled toward 0.5."""
        from ml_pipeline.training.losses import ProxyRegressionLoss

        loss_fn = ProxyRegressionLoss(smoothing=0.1)
        logits = torch.ones(4, 1) * 2.0

        hard_labels = torch.ones(4, 1)
        loss_hard = loss_fn(logits, hard_labels)

        loss_fn_no_smooth = ProxyRegressionLoss(smoothing=0.0)
        loss_no_smooth = loss_fn_no_smooth(logits, hard_labels)

        # Smoothed loss should differ from unsmoothed
        assert abs(loss_hard.item() - loss_no_smooth.item()) > 1e-4
