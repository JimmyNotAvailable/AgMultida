"""Smoke test: model forward pass with dummy data.

Validates that MultimodalStressNet produces correct output shapes
matching onnx_io_contract.yaml: logits [B,1], attention_weights [B,49].
Uses random tensors -- no real data required.
Run: pytest tests/ml/test_model_forward.py -v
"""
from __future__ import annotations

import torch
import pytest


def _make_dummy_batch(batch_size: int = 2):
    return {
        "image": torch.randn(batch_size, 4, 224, 224),
        "sensor_seq": torch.randn(batch_size, 48, 8),
        "weather_ctx": torch.randn(batch_size, 6),
        "modality_mask": torch.ones(batch_size, 3),
    }


class TestModelForward:
    def test_output_shapes(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=2)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.shape == (2, 1), f"Expected [2,1], got {logits.shape}"
        assert attn_weights.shape == (2, 49), f"Expected [2,49], got {attn_weights.shape}"

    def test_output_dtypes(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.dtype == torch.float32
        assert attn_weights.dtype == torch.float32

    def test_missing_modality_no_crash(self):
        """Model must not crash when a modality is masked out."""
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=2)
        batch["modality_mask"] = torch.tensor([[1, 0, 1], [0, 1, 0]], dtype=torch.float32)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.shape == (2, 1)

    def test_batch_size_one(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.shape == (1, 1)
        assert attn_weights.shape == (1, 49)
