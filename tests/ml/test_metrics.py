"""Tests for training metrics."""
from __future__ import annotations

import math

import pytest
import torch

from ml_pipeline.training.metrics import BinaryMetrics, ContinuousMetrics


class TestContinuousMetrics:
    def test_continuous_metrics_exact_values(self):
        metrics = ContinuousMetrics()
        logits = torch.tensor([[0.0], [0.0]])
        labels = torch.tensor([[0.0], [1.0]])

        metrics.update(logits, labels)
        results = metrics.compute()

        assert results["mae"] == pytest.approx(0.5, rel=1e-6)
        assert results["mse"] == pytest.approx(0.25, rel=1e-6)
        assert results["rmse"] == pytest.approx(0.5, rel=1e-6)

    def test_reset_clears_state(self):
        metrics = ContinuousMetrics()
        metrics.update(torch.tensor([[0.0]]), torch.tensor([[1.0]]))
        metrics.reset()
        with pytest.raises(ValueError, match="No predictions accumulated"):
            metrics.compute()


class TestBinaryMetrics:
    def test_perfect_predictions(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[10.0], [-10.0], [10.0], [-10.0]])
        labels = torch.tensor([[1.0], [0.0], [1.0], [0.0]])

        metrics.update(logits, labels)
        results = metrics.compute()

        assert results["binary_accuracy"] == 1.0
        assert results["binary_f1"] == 1.0
        assert results["binary_auc_roc"] == 1.0

    def test_all_wrong_predictions(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[-10.0], [10.0], [-10.0], [10.0]])
        labels = torch.tensor([[1.0], [0.0], [1.0], [0.0]])

        metrics.update(logits, labels)
        results = metrics.compute()

        assert results["binary_accuracy"] == 0.0
        assert results["binary_f1"] == 0.0
        assert results["binary_precision"] == 0.0

    def test_single_class_targets_return_nan_auc(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[0.0], [0.0]])
        labels = torch.tensor([[1.0], [1.0]])

        metrics.update(logits, labels)
        results = metrics.compute()

        assert math.isnan(results["binary_auc_roc"])

    def test_reset_clears_state(self):
        metrics = BinaryMetrics()
        metrics.update(torch.tensor([[10.0]]), torch.tensor([[1.0]]))
        metrics.reset()
        with pytest.raises(ValueError, match="No predictions accumulated"):
            metrics.compute()
