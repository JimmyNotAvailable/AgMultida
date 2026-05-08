"""Tests for calibration and missing-modality evaluation."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from ml_pipeline.evaluation.calibration import (
    compute_calibration_bins,
    expected_calibration_error,
)
from ml_pipeline.evaluation.missing_modality import evaluate_missing_modality


class TinyModel(nn.Module):
    def forward(self, image, sensor_seq, weather_ctx, modality_mask):
        del sensor_seq, weather_ctx
        logits = image.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1)
        logits = logits + modality_mask.sum(dim=1, keepdim=True) * 0.1
        attention = torch.zeros(image.size(0), 49, dtype=image.dtype, device=image.device)
        return logits, attention


def _make_batches():
    return [
        {
            "image": torch.tensor(
                [
                    [[[1.0]]],
                    [[[-1.0]]],
                ]
            ),
            "sensor_seq": torch.zeros(2, 1, 1),
            "weather_ctx": torch.zeros(2, 1),
            "modality_mask": torch.ones(2, 3),
            "label": torch.tensor([[1.0], [0.0]]),
        }
    ]


class TestCalibration:
    def test_calibration_bins_have_expected_counts(self):
        probs = np.array([0.1, 0.2, 0.8, 0.9])
        labels = np.array([0.0, 0.0, 1.0, 1.0])

        bins = compute_calibration_bins(probs, labels, num_bins=2)

        assert bins[0]["count"] == 2.0
        assert bins[1]["count"] == 2.0
        assert bins[0]["accuracy"] == 0.0
        assert bins[1]["accuracy"] == 1.0

    def test_expected_calibration_error_perfect_confidence(self):
        probs = np.array([0.0, 1.0])
        labels = np.array([0.0, 1.0])

        ece = expected_calibration_error(probs, labels, num_bins=2)

        assert ece == 0.0

    def test_calibration_rejects_invalid_probability(self):
        probs = np.array([1.2])
        labels = np.array([1.0])

        try:
            compute_calibration_bins(probs, labels)
        except ValueError as exc:
            assert "probabilities must be in [0, 1]" in str(exc)
        else:
            raise AssertionError("Expected ValueError")


class TestMissingModality:
    def test_missing_modality_returns_metrics_per_pattern(self):
        model = TinyModel()
        batches = _make_batches()
        loss_fn = nn.BCEWithLogitsLoss()
        patterns = {
            "all_present": [1.0, 1.0, 1.0],
            "image_only": [1.0, 0.0, 0.0],
        }

        results = evaluate_missing_modality(model, batches, loss_fn, patterns=patterns)

        assert set(results) == {"all_present", "image_only"}
        assert results["all_present"]["num_samples"] == 2.0
        assert 0.0 <= results["all_present"]["accuracy"] <= 1.0
        assert results["all_present"]["loss"] > 0.0
