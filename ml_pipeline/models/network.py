"""End-to-end MultimodalStressNet: encoders + fusion + head.

Composes all encoder modules into a single nn.Module that takes
raw inputs matching data_contract.yaml and produces outputs
matching onnx_io_contract.yaml.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from ml_pipeline.models.image_encoder import ImageEncoder
from ml_pipeline.models.temporal_encoder import TemporalEncoder
from ml_pipeline.models.weather_encoder import WeatherEncoder
from ml_pipeline.models.fusion import CrossAttentionFusion, FusionHead, ModalityDropout


class MultimodalStressNet(nn.Module):
    """Multimodal water stress detection network.

    Architecture:
        Image  [B,4,224,224] -> EfficientNet-B3 -> [B,256]
        Sensor [B,48,8]      -> GRU+Attention   -> [B,48,256] seq, [B,256] summary
        Weather [B,6]         -> MLP             -> [B,1,256]
        ModalityDropout(p=0.3) on all embeddings
        CrossAttention(Q=image, KV=sensor_seq||weather) -> [B,256]
        FusionHead(concat 768 -> 256 -> 1) -> logits [B,1]
    """

    def __init__(
        self,
        d_model: int = 256,
        num_heads: int = 4,
        sensor_input_dim: int = 8,
        sensor_hidden_dim: int = 128,
        sensor_num_layers: int = 2,
        sensor_dropout: float = 0.3,
        weather_input_dim: int = 6,
        weather_hidden_dim: int = 64,
        modality_dropout_p: float = 0.3,
        fusion_dropout: float = 0.3,
        pretrained_backbone: bool = True,
    ) -> None:
        super().__init__()
        self.image_encoder = ImageEncoder(d_model=d_model, pretrained=pretrained_backbone)
        self.temporal_encoder = TemporalEncoder(
            input_dim=sensor_input_dim,
            hidden_dim=sensor_hidden_dim,
            num_layers=sensor_num_layers,
            dropout=sensor_dropout,
            d_model=d_model,
        )
        self.weather_encoder = WeatherEncoder(
            input_dim=weather_input_dim,
            hidden_dim=weather_hidden_dim,
            d_model=d_model,
        )
        self.modality_dropout = ModalityDropout(p=modality_dropout_p)
        self.cross_attention = CrossAttentionFusion(
            d_model=d_model, num_heads=num_heads,
        )
        self.head = FusionHead(d_model=d_model, dropout=fusion_dropout)

    def forward(
        self,
        image: torch.Tensor,
        sensor_seq: torch.Tensor,
        weather_ctx: torch.Tensor,
        modality_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Full forward pass.

        Args:
            image: [B, 4, 224, 224]
            sensor_seq: [B, 48, 8]
            weather_ctx: [B, 6]
            modality_mask: [B, 3]

        Returns:
            logits: [B, 1] raw logits (no sigmoid).
            attention_weights: [B, 49] cross-attention weights for XAI.
        """
        img_emb = self.image_encoder(image).unsqueeze(1)       # [B, 1, d_model]
        sensor_seq_emb, _, _ = self.temporal_encoder(sensor_seq)  # [B, 48, d_model]
        weather_emb = self.weather_encoder(weather_ctx)          # [B, 1, d_model]

        img_emb, sensor_seq_emb, weather_emb, effective_mask = self.modality_dropout(
            img_emb, sensor_seq_emb, weather_emb, modality_mask,
        )

        kv = torch.cat([sensor_seq_emb, weather_emb], dim=1)  # [B, 49, d_model]
        sensor_missing = effective_mask[:, 1:2].eq(0).expand(-1, sensor_seq_emb.size(1))
        weather_missing = effective_mask[:, 2:3].eq(0)
        key_padding_mask = torch.cat([sensor_missing, weather_missing], dim=1)
        all_kv_missing = key_padding_mask.all(dim=1)
        safe_key_padding_mask = key_padding_mask.clone()
        safe_key_padding_mask[all_kv_missing, -1] = False
        attended, attn_weights = self.cross_attention(
            img_emb,
            kv,
            key_padding_mask=safe_key_padding_mask,
        )  # [B, d_model], [B, 49]
        attended = attended.masked_fill(all_kv_missing.unsqueeze(-1), 0.0)
        attn_weights = attn_weights.masked_fill(key_padding_mask, 0.0)

        fused = torch.cat([
            img_emb.squeeze(1),   # [B, d_model]
            attended,             # [B, d_model]
            weather_emb.squeeze(1),  # [B, d_model]
        ], dim=-1)  # [B, d_model * 3]

        logits = self.head(fused)  # [B, 1]
        return logits, attn_weights
