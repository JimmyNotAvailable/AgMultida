"""EfficientNet-B3 image encoder with 4-channel stem (RGB + NIR).

NIR channel weights initialized as mean of pretrained RGB weights
to leverage ImageNet features while accepting Sentinel-2 4-band input.
Output: [B, 256] embedding projected from EfficientNet-B3 feature dim.
"""
from __future__ import annotations

import torch
import torch.nn as nn

try:
    import timm
except ImportError:
    timm = None  # type: ignore[assignment]


class ImageEncoder(nn.Module):
    """EfficientNet-B3 backbone modified for 4-channel satellite imagery."""

    def __init__(self, d_model: int = 256, pretrained: bool = True) -> None:
        super().__init__()
        if timm is None:
            raise ImportError("timm is required for ImageEncoder: pip install timm")

        self.backbone = timm.create_model(
            "efficientnet_b3",
            pretrained=pretrained,
            num_classes=0,  # remove classifier head
        )
        self._adapt_stem_to_4ch()
        feature_dim = self.backbone.num_features  # 1536 for efficientnet_b3
        self.proj = nn.Linear(feature_dim, d_model)

    def _adapt_stem_to_4ch(self) -> None:
        """Modify first conv to accept 4 channels, init NIR from RGB mean."""
        old_conv = self.backbone.conv_stem
        new_conv = nn.Conv2d(
            4,
            old_conv.out_channels,
            kernel_size=old_conv.kernel_size,
            stride=old_conv.stride,
            padding=old_conv.padding,
            bias=old_conv.bias is not None,
        )
        with torch.no_grad():
            # Copy RGB weights
            new_conv.weight[:, :3, :, :] = old_conv.weight
            # NIR channel: mean of RGB channels
            new_conv.weight[:, 3:4, :, :] = old_conv.weight.mean(dim=1, keepdim=True)
            if old_conv.bias is not None:
                new_conv.bias = old_conv.bias
        self.backbone.conv_stem = new_conv

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: [B, 4, 224, 224] float32 Sentinel-2 RGB+NIR patch.

        Returns:
            [B, d_model] image embedding.
        """
        features = self.backbone(x)  # [B, 1536]
        return self.proj(features)    # [B, 256]
