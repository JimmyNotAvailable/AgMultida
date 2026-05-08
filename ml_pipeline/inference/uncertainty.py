"""MC Dropout wrapper for PyTorch models.

Provides a helper to run inference multiple times with dropout enabled
to estimate epistemic uncertainty.
"""
from __future__ import annotations

import torch
import torch.nn as nn


def predict_with_mc_dropout(
    model: nn.Module,
    inputs: dict[str, torch.Tensor],
    passes: int = 10,
) -> dict[str, torch.Tensor]:
    """Run MC Dropout inference on a batch.

    Args:
        model: The MultimodalStressNet or similar PyTorch model.
        inputs: Dictionary of input tensors (image, sensor_seq, weather_ctx, modality_mask).
        passes: Number of forward passes to perform.

    Returns:
        dict with:
            - 'prob_mean': [B, 1] Mean probability across passes.
            - 'prob_variance': [B, 1] Variance of probabilities across passes.
            - 'logits_mean': [B, 1] Mean raw logits across passes.
            - 'attention_weights_mean': [B, 49] Mean attention weights.
    """
    if passes <= 0:
        raise ValueError("passes must be positive")

    was_training = model.training
    model.train()  # Ensure dropout is active

    all_logits = []
    all_probs = []
    all_attn = []

    with torch.no_grad():
        for _ in range(passes):
            logits, attn_weights = model(**inputs)
            all_logits.append(logits)
            all_probs.append(torch.sigmoid(logits))
            all_attn.append(attn_weights)

    # Stack to [passes, B, ...]
    stacked_logits = torch.stack(all_logits, dim=0)
    stacked_probs = torch.stack(all_probs, dim=0)
    stacked_attn = torch.stack(all_attn, dim=0)

    result = {
        "prob_mean": stacked_probs.mean(dim=0),
        "prob_variance": stacked_probs.var(dim=0, unbiased=passes > 1),
        "logits_mean": stacked_logits.mean(dim=0),
        "attention_weights_mean": stacked_attn.mean(dim=0),
    }
    model.train(was_training)
    return result
