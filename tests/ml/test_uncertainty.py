"""Tests for MC Dropout wrapper."""
from __future__ import annotations

import torch

from ml_pipeline.inference.uncertainty import predict_with_mc_dropout


class TinyDropoutModel(torch.nn.Module):
    def __init__(self, dropout_p: float = 0.5) -> None:
        super().__init__()
        self.dropout = torch.nn.Dropout(p=dropout_p)
        self.linear = torch.nn.Linear(3, 1)

    def forward(self, image, sensor_seq, weather_ctx, modality_mask):
        del sensor_seq, weather_ctx
        features = image.flatten(start_dim=1)[:, :3] + modality_mask
        logits = self.linear(self.dropout(features))
        attention = torch.zeros(image.size(0), 49, dtype=image.dtype, device=image.device)
        return logits, attention


def _make_dummy_batch(batch_size: int = 2):
    return {
        "image": torch.randn(batch_size, 1, 2, 2),
        "sensor_seq": torch.randn(batch_size, 1, 1),
        "weather_ctx": torch.randn(batch_size, 1),
        "modality_mask": torch.ones(batch_size, 3),
    }


class TestMCDropout:
    def test_predict_shapes(self):
        model = TinyDropoutModel()
        batch = _make_dummy_batch(batch_size=2)

        res = predict_with_mc_dropout(model, batch, passes=5)

        assert "prob_mean" in res
        assert "prob_variance" in res
        assert "logits_mean" in res
        assert "attention_weights_mean" in res

        assert res["prob_mean"].shape == (2, 1)
        assert res["prob_variance"].shape == (2, 1)
        assert res["logits_mean"].shape == (2, 1)
        assert res["attention_weights_mean"].shape == (2, 49)

    def test_variance_is_non_negative(self):
        model = TinyDropoutModel()
        batch = _make_dummy_batch(batch_size=3)

        res = predict_with_mc_dropout(model, batch, passes=10)

        assert torch.all(res["prob_variance"] >= 0.0)

    def test_dropout_behavior_makes_predictions_vary(self):
        model = TinyDropoutModel(dropout_p=0.9)
        batch = _make_dummy_batch(batch_size=1)

        res = predict_with_mc_dropout(model, batch, passes=10)

        assert torch.all(res["prob_variance"] > 1e-6)
