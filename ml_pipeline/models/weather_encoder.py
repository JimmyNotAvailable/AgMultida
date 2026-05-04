"""Weather context MLP encoder.

Processes fixed-dim [B, 6] weather context vector (padded from 2..6 features).
Uses LayerNorm + GELU per architecture spec.
Output: [B, 1, d_model] for cross-attention KV concatenation with sensor seq.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class WeatherEncoder(nn.Module):
    """MLP encoder for weather context vector."""

    def __init__(
        self,
        input_dim: int = 6,
        hidden_dim: int = 64,
        d_model: int = 256,
    ) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: [B, 6] weather context (padded, unused dims = 0.0).

        Returns:
            [B, 1, d_model] weather embedding (unsqueezed for KV concat).
        """
        emb = self.mlp(x)          # [B, d_model]
        return emb.unsqueeze(1)    # [B, 1, d_model]
