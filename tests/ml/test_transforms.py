"""Tests for contract-safe training transforms.

Run: pytest tests/ml/test_transforms.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.data.transforms import ComposeTransforms, ImageRandomFlip, SensorGaussianNoise


def _make_batch() -> dict[str, torch.Tensor]:
    return {
        "image": torch.arange(4 * 224 * 224, dtype=torch.float32).reshape(4, 224, 224),
        "sensor_seq": torch.ones(48, 8, dtype=torch.float32),
        "weather_ctx": torch.arange(6, dtype=torch.float32),
        "modality_mask": torch.tensor([1.0, 0.0, 1.0], dtype=torch.float32),
        "label": torch.tensor([0.5], dtype=torch.float32),
    }


def test_image_flip_preserves_contract_and_mask_semantics() -> None:
    batch = _make_batch()
    transformed = ImageRandomFlip(horizontal_p=1.0, vertical_p=0.0)(batch)

    assert transformed["image"].shape == batch["image"].shape
    assert transformed["image"].dtype == torch.float32
    assert torch.equal(transformed["image"], torch.flip(batch["image"], dims=(-1,)))
    assert torch.equal(transformed["modality_mask"], batch["modality_mask"])
    assert transformed["modality_mask"].dtype == torch.float32


def test_sensor_noise_preserves_shape_dtype_and_missing_sensor_zero_fill() -> None:
    batch = _make_batch()
    transformed = SensorGaussianNoise(std=0.5, seed=7)(batch)

    assert transformed["sensor_seq"].shape == batch["sensor_seq"].shape
    assert transformed["sensor_seq"].dtype == torch.float32
    assert torch.equal(transformed["sensor_seq"], torch.zeros_like(batch["sensor_seq"]))
    assert torch.equal(transformed["modality_mask"], batch["modality_mask"])


def test_compose_preserves_all_tensor_shapes_and_dtypes() -> None:
    batch = _make_batch()
    transform = ComposeTransforms([
        ImageRandomFlip(horizontal_p=1.0, vertical_p=1.0),
        SensorGaussianNoise(std=0.01, seed=11),
    ])

    transformed = transform(batch)

    for key, tensor in batch.items():
        assert transformed[key].shape == tensor.shape
        assert transformed[key].dtype == tensor.dtype
    assert torch.equal(transformed["weather_ctx"], batch["weather_ctx"])
    assert torch.equal(transformed["modality_mask"], batch["modality_mask"])
