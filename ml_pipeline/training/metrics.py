"""Binary classification metrics computation for training evaluation.

Accumulates predictions and computes accuracy, precision, recall,
F1 score, AUC-ROC, and AUC-PR using sklearn.
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class BinaryMetrics:
    """Accumulates predictions and computes binary classification metrics.

    Thread-safe-ish (via list append, no shared tensor state).
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.reset()

    def reset(self) -> None:
        """Clear accumulated predictions."""
        self._preds_probs: list[float] = []
        self._targets: list[float] = []

    def update(self, logits: torch.Tensor, targets: torch.Tensor) -> None:
        """Accumulate predictions from a batch.

        Args:
            logits: [B, 1] raw model outputs.
            targets: [B, 1] ground truth labels in [0, 1].
        """
        probs = torch.sigmoid(logits).detach().cpu().numpy().flatten()
        labels = targets.detach().cpu().numpy().flatten()

        self._preds_probs.extend(probs.tolist())
        self._targets.extend(labels.tolist())

    def compute(self) -> dict[str, float]:
        """Compute metrics over all accumulated predictions.

        Returns:
            Dict containing accuracy, precision, recall, f1, auc_roc, auc_pr.
        """
        if not self._targets:
            raise ValueError("No predictions accumulated, cannot compute metrics.")

        raw_targets = np.array(self._targets)
        y_prob = np.array(self._preds_probs)
        
        # Binarize targets and predictions for classification metrics
        y_true = (raw_targets >= self.threshold).astype(float)
        y_pred = (y_prob >= self.threshold).astype(float)

        # Handle edge cases (e.g., only one class present in targets)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                auc_roc = float(roc_auc_score(y_true, y_prob))
            except ValueError:
                auc_roc = 0.5  # Default if only one class in y_true

            try:
                auc_pr = float(average_precision_score(y_true, y_prob))
            except ValueError:
                auc_pr = 0.0

        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "auc_roc": auc_roc,
            "auc_pr": auc_pr,
        }
