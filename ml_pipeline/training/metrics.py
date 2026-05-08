"""Training metrics for continuous proxy labels and optional binary diagnostics."""
from __future__ import annotations

import math
import warnings

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


class ContinuousMetrics:
    """Accumulates predictions and computes continuous-label metrics."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._preds_probs: list[float] = []
        self._targets: list[float] = []

    def update(self, logits: torch.Tensor, targets: torch.Tensor) -> None:
        probs = torch.sigmoid(logits).detach().cpu().numpy().flatten()
        labels = targets.detach().cpu().numpy().flatten()
        self._preds_probs.extend(probs.tolist())
        self._targets.extend(labels.tolist())

    def compute(self) -> dict[str, float]:
        if not self._targets:
            raise ValueError("No predictions accumulated, cannot compute metrics.")

        y_true = np.array(self._targets, dtype=np.float32)
        y_prob = np.array(self._preds_probs, dtype=np.float32)
        diff = y_prob - y_true
        mse = float(np.mean(np.square(diff)))
        mae = float(np.mean(np.abs(diff)))
        rmse = float(math.sqrt(mse))
        return {
            "mae": mae,
            "rmse": rmse,
            "mse": mse,
        }


class BinaryMetrics:
    """Accumulates predictions and computes thresholded binary diagnostics."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self.reset()

    def reset(self) -> None:
        self._preds_probs: list[float] = []
        self._targets: list[float] = []

    def update(self, logits: torch.Tensor, targets: torch.Tensor) -> None:
        probs = torch.sigmoid(logits).detach().cpu().numpy().flatten()
        labels = targets.detach().cpu().numpy().flatten()
        self._preds_probs.extend(probs.tolist())
        self._targets.extend(labels.tolist())

    def compute(self) -> dict[str, float]:
        if not self._targets:
            raise ValueError("No predictions accumulated, cannot compute metrics.")

        raw_targets = np.array(self._targets)
        y_prob = np.array(self._preds_probs)
        y_true = (raw_targets >= self.threshold).astype(float)
        y_pred = (y_prob >= self.threshold).astype(float)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                auc_roc = float(roc_auc_score(y_true, y_prob))
            except ValueError:
                auc_roc = float("nan")

            try:
                auc_pr = float(average_precision_score(y_true, y_prob))
            except ValueError:
                auc_pr = float("nan")

        return {
            "binary_accuracy": float(accuracy_score(y_true, y_pred)),
            "binary_precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "binary_recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "binary_f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "binary_auc_roc": auc_roc,
            "binary_auc_pr": auc_pr,
        }
