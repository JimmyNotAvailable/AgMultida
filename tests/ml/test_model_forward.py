"""Smoke test: model forward pass with dummy data.

Validates that MultimodalStressNet produces correct output shapes
matching onnx_io_contract.yaml: logits [B,1], attention_weights [B,49].
Uses random tensors -- no real data required.
Run: pytest tests/ml/test_model_forward.py -v
"""
from __future__ import annotations

import torch


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
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=2)
        batch["modality_mask"] = torch.tensor([[1, 0, 1], [0, 1, 0]], dtype=torch.float32)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.shape == (2, 1)
        assert attn_weights.shape == (2, 49)

    def test_masked_sensor_values_do_not_affect_output(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)
        batch["modality_mask"] = torch.tensor([[1, 0, 1]], dtype=torch.float32)

        changed_batch = {
            **batch,
            "sensor_seq": torch.randn_like(batch["sensor_seq"]) * 1000.0,
        }

        with torch.no_grad():
            logits, attn_weights = model(**batch)
            changed_logits, changed_attn_weights = model(**changed_batch)

        assert torch.allclose(logits, changed_logits, atol=1e-5)
        assert torch.allclose(attn_weights[:, :48], changed_attn_weights[:, :48], atol=1e-5)

    def test_masked_weather_values_do_not_affect_output(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)
        batch["modality_mask"] = torch.tensor([[1, 1, 0]], dtype=torch.float32)

        changed_batch = {
            **batch,
            "weather_ctx": torch.randn_like(batch["weather_ctx"]) * 1000.0,
        }

        with torch.no_grad():
            logits, attn_weights = model(**batch)
            changed_logits, changed_attn_weights = model(**changed_batch)

        assert torch.allclose(logits, changed_logits, atol=1e-5)
        assert torch.allclose(attn_weights[:, 48:], changed_attn_weights[:, 48:], atol=1e-5)

    def test_batch_size_one(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)

        with torch.no_grad():
            logits, attn_weights = model(**batch)

        assert logits.shape == (1, 1)
        assert attn_weights.shape == (1, 49)

    def test_all_kv_missing_returns_zero_attention(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False)
        model.eval()
        batch = _make_dummy_batch(batch_size=1)
        batch["modality_mask"] = torch.tensor([[1, 0, 0]], dtype=torch.float32)

        with torch.no_grad():
            _, attn_weights = model(**batch)

        assert torch.count_nonzero(attn_weights) == 0

    def test_training_dropout_masks_attention_weights(self):
        from ml_pipeline.models.network import MultimodalStressNet

        model = MultimodalStressNet(pretrained_backbone=False, modality_dropout_p=1.0)
        model.train()
        batch = _make_dummy_batch(batch_size=1)

        logits, attn_weights = model(**batch)

        assert logits.shape == (1, 1)
        assert attn_weights.shape == (1, 49)
        assert logits.requires_grad
        assert torch.isfinite(logits).all()
        assert torch.isfinite(attn_weights).all()
        assert torch.count_nonzero(attn_weights) == 0
        assert torch.allclose(attn_weights, torch.zeros_like(attn_weights), atol=1e-6)
        assert torch.allclose(attn_weights.sum(dim=1), torch.zeros(1), atol=1e-6)
