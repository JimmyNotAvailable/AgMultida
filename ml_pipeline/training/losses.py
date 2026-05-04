"""Loss functions for multimodal stress detection training.

BCEWithLogitsLoss with pos_weight for class imbalance (60/40 healthy/stressed).
Manual label smoothing because BCEWithLogitsLoss has no native support.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class SmoothedBCEWithLogitsLoss(nn.Module):
    """BCEWithLogitsLoss with manual label smoothing.

    Label smoothing for binary classification:
        smoothed_label = label * (1 - smoothing) + 0.5 * smoothing

    This pulls labels slightly toward 0.5, reducing overconfidence.
    Combined with pos_weight for class imbalance handling.
    """

    def __init__(
        self,
        pos_weight: float = 1.5,
        smoothing: float = 0.1,
    ) -> None:
        super().__init__()
        self.smoothing = smoothing
        self.loss_fn = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor([pos_weight]),
        )

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute smoothed BCE loss.

        Args:
            logits: [B, 1] raw model output.
            targets: [B, 1] ground truth labels in [0, 1].

        Returns:
            Scalar loss tensor.
        """
        if self.smoothing > 0.0:
            targets = targets * (1.0 - self.smoothing) + 0.5 * self.smoothing

        # JUN: Move pos_weight to same device as logits
        if self.loss_fn.pos_weight.device != logits.device:
            self.loss_fn.pos_weight = self.loss_fn.pos_weight.to(logits.device)

        return self.loss_fn(logits, targets)
