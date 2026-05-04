"""GRU temporal encoder with learnable temporal attention.

Processes 48-hour environmental sensor sequences [B, 48, 8].
Temporal attention uses a learnable query vector to weight hidden states,
capturing which timesteps are most relevant for stress detection.
Output: [B, 48, d_model] full sequence + [B, d_model] attended summary.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TemporalAttention(nn.Module):
    """Learnable attention over GRU hidden states."""

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.query = nn.Parameter(torch.randn(hidden_dim))
        self.scale = hidden_dim ** 0.5

    def forward(self, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute attention-weighted summary of hidden states.

        Args:
            h: [B, T, hidden_dim] GRU outputs.

        Returns:
            context: [B, hidden_dim] attended summary.
            weights: [B, T] attention weights.
        """
        scores = torch.matmul(h, self.query) / self.scale  # [B, T]
        weights = F.softmax(scores, dim=-1)                 # [B, T]
        context = torch.bmm(weights.unsqueeze(1), h).squeeze(1)  # [B, hidden_dim]
        return context, weights


class TemporalEncoder(nn.Module):
    """GRU encoder for environmental sensor sequences."""

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        d_model: int = 256,
    ) -> None:
        super().__init__()
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attention = TemporalAttention(hidden_dim)
        self.proj = nn.Linear(hidden_dim, d_model)
        self.seq_proj = nn.Linear(hidden_dim, d_model)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            x: [B, 48, 8] sensor sequence.

        Returns:
            seq_emb: [B, 48, d_model] full sequence embeddings (for KV in cross-attention).
            summary: [B, d_model] attended summary.
            attn_weights: [B, 48] temporal attention weights.
        """
        h, _ = self.gru(x)                           # [B, 48, hidden_dim]
        summary, attn_weights = self.attention(h)     # [B, hidden_dim], [B, 48]
        summary = self.proj(summary)                  # [B, d_model]
        seq_emb = self.seq_proj(h)                    # [B, 48, d_model]
        return seq_emb, summary, attn_weights
