"""Evaluate model quality when modalities are missing.

Runs a model in eval mode with each modality-mask permutation
and collects per-pattern accuracy and loss.
"""
from __future__ import annotations

from typing import Sequence

import torch
import torch.nn as nn


# Standard patterns: image, sensor, weather
MODALITY_PATTERNS = {
    "all_present": [1.0, 1.0, 1.0],
    "image_only": [1.0, 0.0, 0.0],
    "sensor_only": [0.0, 1.0, 0.0],
    "weather_only": [0.0, 0.0, 1.0],
    "no_image": [0.0, 1.0, 1.0],
    "no_sensor": [1.0, 0.0, 1.0],
    "no_weather": [1.0, 1.0, 0.0],
}


@torch.no_grad()
def evaluate_missing_modality(
    model: nn.Module,
    batches: Sequence[dict[str, torch.Tensor]],
    loss_fn: nn.Module,
    patterns: dict[str, list[float]] | None = None,
    threshold: float = 0.5,
) -> dict[str, dict[str, float]]:
    """Evaluate model under each modality-mask pattern.

    Args:
        model: Model to evaluate (must accept `modality_mask` kwarg).
        batches: Iterable of batch dicts with keys image, sensor_seq,
            weather_ctx, modality_mask, label.
        loss_fn: Loss criterion returning scalar.
        patterns: Dict mapping pattern name -> [3] mask values.
            Defaults to MODALITY_PATTERNS.
        threshold: Classification threshold.

    Returns:
        Dict mapping pattern name -> dict with loss, accuracy, num_samples.
    """
    if patterns is None:
        patterns = MODALITY_PATTERNS

    model.eval()
    results: dict[str, dict[str, float]] = {}

    for pattern_name, mask_values in patterns.items():
        total_loss = 0.0
        correct = 0
        total = 0

        for batch in batches:
            batch_size = batch["image"].size(0)
            forced_mask = torch.tensor(
                [mask_values], dtype=torch.float32,
            ).expand(batch_size, -1).to(batch["image"].device)

            inputs = {
                "image": batch["image"],
                "sensor_seq": batch["sensor_seq"],
                "weather_ctx": batch["weather_ctx"],
                "modality_mask": forced_mask,
            }
            labels = batch["label"]

            logits, _ = model(**inputs)
            loss = loss_fn(logits, labels)

            preds = (torch.sigmoid(logits) >= threshold).float()
            binary_labels = (labels >= threshold).float()
            correct += int((preds == binary_labels).sum().item())
            total += batch_size
            total_loss += loss.item() * batch_size

        avg_loss = total_loss / max(total, 1)
        accuracy = correct / max(total, 1)

        results[pattern_name] = {
            "loss": avg_loss,
            "accuracy": accuracy,
            "num_samples": float(total),
        }

    return results
