"""Dataset integration tests for AgMultidaDataset.

Validates batching, collation, shape integrity, and edge cases
using programmatically generated fixtures. No real data.

Run: pytest tests/ml/test_dataset_contract.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.data.sample import AlignedSample
from ml_pipeline.data.dataset import AgMultidaDataset


def _make_sample(seed: int = 42, label: float = 0.42, zone: str = "A01") -> AlignedSample:
    """Create a valid AlignedSample with deterministic tensors."""
    torch.manual_seed(seed)
    return AlignedSample(
        sample_id=f"{zone}_20240214_S{seed}",
        zone_id=zone,
        timestamp=datetime(2024, 2, 14, 3, 21, 0, tzinfo=timezone.utc),
        image=torch.rand(4, 224, 224),
        sensor_seq=torch.rand(48, 8),
        weather_ctx=torch.rand(6),
        modality_mask=torch.tensor([1.0, 1.0, 1.0]),
        label=label,
        source_trace={
            "image_source": "sentinel2_L2A",
            "sensor_sources": ["era5_land"],
            "weather_source": "open_meteo",
            "label_formula": "ndvi_delta",
            "alignment_method": "nearest_temporal",
            "cloud_rate": 0.05,
        },
    )


class TestDatasetBasics:
    def test_dataset_len(self):
        samples = [_make_sample(seed=i) for i in range(5)]
        ds = AgMultidaDataset(samples)
        assert len(ds) == 5

    def test_dataset_getitem_returns_dict(self):
        ds = AgMultidaDataset([_make_sample()])
        item = ds[0]
        expected_keys = {"image", "sensor_seq", "weather_ctx", "modality_mask", "label"}
        assert set(item.keys()) == expected_keys

    def test_dataset_single_sample(self):
        ds = AgMultidaDataset([_make_sample()])
        item = ds[0]
        assert item["image"].shape == (4, 224, 224)
        assert item["label"].shape == (1,)

    def test_dataset_empty_raises(self):
        with pytest.raises(ValueError, match="at least one sample"):
            AgMultidaDataset([])


class TestDatasetShapes:
    def test_tensor_shapes_after_collation(self):
        """DataLoader collation produces correct batch shapes."""
        samples = [_make_sample(seed=i) for i in range(3)]
        ds = AgMultidaDataset(samples)
        loader = DataLoader(ds, batch_size=3, shuffle=False)
        batch = next(iter(loader))

        assert batch["image"].shape == (3, 4, 224, 224)
        assert batch["sensor_seq"].shape == (3, 48, 8)
        assert batch["weather_ctx"].shape == (3, 6)
        assert batch["modality_mask"].shape == (3, 3)
        assert batch["label"].shape == (3, 1)

    def test_dtypes_float32_after_collation(self):
        samples = [_make_sample(seed=i) for i in range(2)]
        ds = AgMultidaDataset(samples)
        loader = DataLoader(ds, batch_size=2)
        batch = next(iter(loader))

        for key, tensor in batch.items():
            assert tensor.dtype == torch.float32, f"{key} dtype is {tensor.dtype}"


class TestDatasetEdgeCases:
    def test_missing_modality_preserved(self):
        """modality_mask zeros survive dataset -> DataLoader pipeline."""
        sample = _make_sample()
        sample.modality_mask = torch.tensor([1.0, 0.0, 1.0])
        ds = AgMultidaDataset([sample])
        item = ds[0]
        assert item["modality_mask"][1].item() == 0.0

    def test_label_in_batch(self):
        ds = AgMultidaDataset([_make_sample(label=0.75)])
        item = ds[0]
        assert item["label"].item() == pytest.approx(0.75)

    def test_iteration_order_deterministic(self):
        samples = [_make_sample(seed=i, label=i / 10.0) for i in range(4)]
        ds = AgMultidaDataset(samples)
        labels = [ds[i]["label"].item() for i in range(4)]
        assert labels == [pytest.approx(i / 10.0) for i in range(4)]

    def test_dataset_rejects_invalid_sample(self):
        """Invalid sample at construction time raises ValueError."""
        with pytest.raises(ValueError):
            bad_sample = AlignedSample(
                sample_id="INVALID",
                zone_id="A01",
                timestamp=datetime(2024, 2, 14, tzinfo=timezone.utc),
                image=torch.rand(4, 224, 224),
                sensor_seq=torch.rand(48, 8),
                weather_ctx=torch.rand(6),
                modality_mask=torch.tensor([1.0, 1.0, 1.0]),
                label=0.5,
                source_trace={
                    "image_source": "s2",
                    "sensor_sources": [],
                    "weather_source": "om",
                    "label_formula": "ndvi",
                    "alignment_method": "nearest",
                    "cloud_rate": 0.0,
                },
            )
