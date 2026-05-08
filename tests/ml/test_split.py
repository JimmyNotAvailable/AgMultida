"""Tests for deterministic spatial-temporal sample splits.

Run: pytest tests/ml/test_split.py -v
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.data.sample import AlignedSample
from ml_pipeline.data.split import split_spatial_temporal
from tests.data_contract.conftest import make_valid_sample_kwargs


def _make_sample(zone: str, day: int, suffix: str) -> AlignedSample:
    kwargs = make_valid_sample_kwargs(seed=day)
    kwargs.update({
        "sample_id": f"{zone}_202402{day:02d}_{suffix}",
        "zone_id": zone,
        "timestamp": datetime(2024, 2, day, 3, 21, 0, tzinfo=timezone.utc),
        "modality_mask": torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
    })
    return AlignedSample(**kwargs)


def _zones(samples: list[AlignedSample]) -> set[str]:
    return {sample.zone_id for sample in samples}


def test_split_is_deterministic_and_has_no_zone_overlap() -> None:
    samples = [
        _make_sample(zone, day, f"S{day}")
        for zone in ("A01", "A02", "A03", "A04", "A05")
        for day in (1, 2)
    ]

    first = split_spatial_temporal(samples, seed=123)
    second = split_spatial_temporal(list(reversed(samples)), seed=123)

    assert [sample.sample_id for sample in first.train] == [sample.sample_id for sample in second.train]
    assert [sample.sample_id for sample in first.val] == [sample.sample_id for sample in second.val]
    assert [sample.sample_id for sample in first.test] == [sample.sample_id for sample in second.test]
    assert _zones(first.train).isdisjoint(_zones(first.val))
    assert _zones(first.train).isdisjoint(_zones(first.test))
    assert _zones(first.val).isdisjoint(_zones(first.test))


def test_split_orders_samples_temporally_within_each_split() -> None:
    samples = [
        _make_sample("A01", 3, "S3"),
        _make_sample("A01", 1, "S1"),
        _make_sample("A02", 2, "S2"),
        _make_sample("A02", 1, "S1"),
        _make_sample("A03", 2, "S2"),
    ]

    split = split_spatial_temporal(samples, train_ratio=0.34, val_ratio=0.33, seed=1)

    for subset in (split.train, split.val, split.test):
        assert subset == sorted(subset, key=lambda sample: (sample.timestamp, sample.zone_id, sample.sample_id))


def test_split_rejects_empty_samples() -> None:
    try:
        split_spatial_temporal([])
    except ValueError as error:
        assert "at least one sample" in str(error)
    else:
        raise AssertionError("expected ValueError")
