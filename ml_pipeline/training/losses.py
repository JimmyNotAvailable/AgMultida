"""Loss functions for multimodal proxy-label training."""
from __future__ import annotations

import torch
import torch.nn as nn


class ProxyRegressionLoss(nn.Module):
    """Mean squared error on sigmoid probabilities for continuous proxy labels."""

    def __init__(self, smoothing: float = 0.0) -> None:
        super().__init__()
        self.smoothing = smoothing
        self.loss_fn = nn.MSELoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if self.smoothing > 0.0:
            targets = targets * (1.0 - self.smoothing) + 0.5 * self.smoothing
        probs = torch.sigmoid(logits)
        return self.loss_fn(probs, targets)
