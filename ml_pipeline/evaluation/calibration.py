"""Calibration utilities for binary classification evaluation."""
from __future__ import annotations

import numpy as np


EPSILON = 1e-12


def compute_calibration_bins(
    probabilities: np.ndarray,
    labels: np.ndarray,
    num_bins: int = 10,
) -> list[dict[str, float]]:
    """Compute calibration bins over [0, 1] probabilities.

    Args:
        probabilities: [N] predicted probabilities.
        labels: [N] binary labels.
        num_bins: Number of equal-width bins.

    Returns:
        List of per-bin dicts containing count, accuracy, confidence, and gap.
    """
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    y_true = np.asarray(labels, dtype=float).reshape(-1)

    if probs.shape[0] != y_true.shape[0]:
        raise ValueError("probabilities and labels must have same length")
    if probs.size == 0:
        raise ValueError("probabilities must not be empty")
    if num_bins <= 0:
        raise ValueError("num_bins must be positive")
    if np.any((probs < 0.0) | (probs > 1.0)):
        raise ValueError("probabilities must be in [0, 1]")

    bin_edges = np.linspace(0.0, 1.0, num_bins + 1)
    bin_indices = np.digitize(probs, bin_edges[1:-1], right=False)

    bins: list[dict[str, float]] = []
    for bin_index in range(num_bins):
        mask = bin_indices == bin_index
        count = int(mask.sum())
        if count == 0:
            bins.append(
                {
                    "bin_lower": float(bin_edges[bin_index]),
                    "bin_upper": float(bin_edges[bin_index + 1]),
                    "count": 0.0,
                    "accuracy": 0.0,
                    "confidence": 0.0,
                    "gap": 0.0,
                }
            )
            continue

        bin_probs = probs[mask]
        bin_labels = y_true[mask]
        confidence = float(bin_probs.mean())
        accuracy = float((bin_labels >= 0.5).mean())
        bins.append(
            {
                "bin_lower": float(bin_edges[bin_index]),
                "bin_upper": float(bin_edges[bin_index + 1]),
                "count": float(count),
                "accuracy": accuracy,
                "confidence": confidence,
                "gap": abs(accuracy - confidence),
            }
        )

    return bins


def expected_calibration_error(
    probabilities: np.ndarray,
    labels: np.ndarray,
    num_bins: int = 10,
) -> float:
    """Compute expected calibration error (ECE)."""
    bins = compute_calibration_bins(probabilities, labels, num_bins=num_bins)
    total_count = sum(bin_stats["count"] for bin_stats in bins)
    if total_count <= EPSILON:
        raise ValueError("total count must be positive")

    ece = sum((bin_stats["count"] / total_count) * bin_stats["gap"] for bin_stats in bins)
    return float(ece)
