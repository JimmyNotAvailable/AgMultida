"""Cross-Attention fusion with ModalityDropout.

One-way cross-attention: image embedding (Query) attends to
sensor sequence + weather token (Key/Value).
ModalityDropout zeros out entire modalities during training (p=0.3)
to force robustness under missing data at inference.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ModalityDropout(nn.Module):
    """Zero out entire modality embeddings during training.

    Each modality is independently dropped with probability p.
    At inference, no dropout is applied -- modality_mask handles real missing data.
    """

    def __init__(self, p: float = 0.3) -> None:
        super().__init__()
        self.p = p

    def forward(
        self,
        image_emb: torch.Tensor,
        sensor_emb: torch.Tensor,
        weather_emb: torch.Tensor,
        modality_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Apply modality dropout.

        Args:
            image_emb: [B, 1, d_model]
            sensor_emb: [B, 48, d_model]
            weather_emb: [B, 1, d_model]
            modality_mask: [B, 3] real availability flags.

        Returns:
            Dropout-masked embeddings (training) or mask-applied embeddings (eval).
        """
        if self.training:
            device = image_emb.device
            drop_mask = torch.bernoulli(
                torch.full((image_emb.size(0), 3), 1.0 - self.p, device=device)
            )
            # Combine training dropout with real modality mask
            effective = drop_mask * modality_mask
        else:
            effective = modality_mask

        image_emb = image_emb * effective[:, 0:1].unsqueeze(-1)
        sensor_emb = sensor_emb * effective[:, 1:2].unsqueeze(-1)
        weather_emb = weather_emb * effective[:, 2:3].unsqueeze(-1)
        return image_emb, sensor_emb, weather_emb


class CrossAttentionFusion(nn.Module):
    """One-way cross-attention: image queries sensor + weather context."""

    def __init__(self, d_model: int = 256, num_heads: int = 4, dropout: float = 0.1) -> None:
        super().__init__()
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(d_model)

    def forward(
        self,
        query: torch.Tensor,
        kv: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Cross-attention forward.

        Args:
            query: [B, 1, d_model] image embedding.
            kv: [B, 49, d_model] concat(sensor_seq[48], weather[1]).

        Returns:
            attended: [B, d_model] cross-attended output.
            attn_weights: [B, 49] attention weights for XAI.
        """
        attn_out, attn_weights = self.cross_attn(
            query=query, key=kv, value=kv,
            need_weights=True, average_attn_weights=True,
        )
        attended = self.norm(attn_out.squeeze(1))  # [B, d_model]
        attn_w = attn_weights.squeeze(1)            # [B, 49]
        return attended, attn_w


class FusionHead(nn.Module):
    """Final MLP head: concat(image, attn_sensor, attn_weather) -> logits."""

    def __init__(self, d_model: int = 256, dropout: float = 0.3) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(d_model * 3, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, 1),
        )

    def forward(self, fused: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            fused: [B, d_model * 3] concatenated embeddings.

        Returns:
            [B, 1] raw logits (no sigmoid).
        """
        return self.mlp(fused)
