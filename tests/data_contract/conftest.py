"""Shared fixtures for data contract tests.

Generates contract-compliant AlignedSample instances using fixed
seed for reproducibility. No real data files, no network access.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import torch


def make_valid_source_trace() -> dict:
    """Return a source_trace dict with all required keys."""
    return {
        "image_source": "sentinel2_L2A",
        "sensor_sources": ["era5_land", "smap"],
        "weather_source": "open_meteo",
        "label_formula": "ndvi_delta_threshold",
        "alignment_method": "nearest_temporal",
        "cloud_rate": 0.05,
    }


def make_valid_sample_kwargs(seed: int = 42) -> dict:
    """Return kwargs dict for constructing a valid AlignedSample.

    Uses torch.manual_seed for reproducibility. All values are
    contract-compliant: correct shapes, dtypes, ranges.
    """
    torch.manual_seed(seed)
    return {
        "sample_id": "A01_20240214_S2",
        "zone_id": "A01",
        "timestamp": datetime(2024, 2, 14, 3, 21, 0, tzinfo=timezone.utc),
        "image": torch.rand(4, 224, 224),
        "sensor_seq": torch.rand(48, 8),
        "weather_ctx": torch.rand(6),
        "modality_mask": torch.tensor([1.0, 1.0, 1.0]),
        "label": 0.42,
        "source_trace": make_valid_source_trace(),
    }


@pytest.fixture
def valid_sample_kwargs():
    """Fixture providing kwargs for a valid AlignedSample."""
    return make_valid_sample_kwargs()
