"""Tests for BinaryMetrics.

Run: pytest tests/ml/test_metrics.py -v
"""
from __future__ import annotations

import pytest
import torch

from ml_pipeline.training.metrics import BinaryMetrics


class TestBinaryMetrics:
    def test_perfect_predictions(self):
        metrics = BinaryMetrics()
        # High logits for 1, low logits for 0
        logits = torch.tensor([[10.0], [-10.0], [10.0], [-10.0]])
        labels = torch.tensor([[1.0], [0.0], [1.0], [0.0]])
        
        metrics.update(logits, labels)
        results = metrics.compute()
        
        assert results["accuracy"] == 1.0
        assert results["f1"] == 1.0
        assert results["auc_roc"] == 1.0

    def test_all_wrong_predictions(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[-10.0], [10.0], [-10.0], [10.0]])
        labels = torch.tensor([[1.0], [0.0], [1.0], [0.0]])
        
        metrics.update(logits, labels)
        results = metrics.compute()
        
        assert results["accuracy"] == 0.0
        # F1 and Precision should handle zero division gracefully (return 0.0)
        assert results["f1"] == 0.0
        assert results["precision"] == 0.0

    def test_mixed_predictions(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[10.0], [10.0], [-10.0], [-10.0]])
        labels = torch.tensor([[1.0], [0.0], [1.0], [0.0]])
        
        metrics.update(logits, labels)
        results = metrics.compute()
        
        assert results["accuracy"] == 0.5
        assert 0.0 < results["auc_roc"] < 1.0

    def test_auc_roc_range(self):
        metrics = BinaryMetrics()
        logits = torch.randn(20, 1)
        labels = torch.randint(0, 2, (20, 1)).float()
        
        metrics.update(logits, labels)
        results = metrics.compute()
        
        assert 0.0 <= results["auc_roc"] <= 1.0

    def test_auc_pr_range(self):
        metrics = BinaryMetrics()
        logits = torch.randn(20, 1)
        labels = torch.randint(0, 2, (20, 1)).float()
        
        metrics.update(logits, labels)
        results = metrics.compute()
        
        assert 0.0 <= results["auc_pr"] <= 1.0

    def test_reset_clears_state(self):
        metrics = BinaryMetrics()
        logits = torch.tensor([[10.0]])
        labels = torch.tensor([[1.0]])
        
        metrics.update(logits, labels)
        metrics.reset()
        
        with pytest.raises(ValueError, match="No predictions accumulated"):
            metrics.compute()
