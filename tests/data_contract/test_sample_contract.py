"""Contract validation tests for AlignedSample.

Each test targets a single contract invariant from data_contract.yaml.
All violations must raise ValueError with a descriptive message.
No silent coercion is allowed.

Run: pytest tests/data_contract/test_sample_contract.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml_pipeline.data.sample import AlignedSample
from tests.data_contract.conftest import make_valid_sample_kwargs


class TestValidSample:
    def test_valid_sample_passes(self):
        kwargs = make_valid_sample_kwargs()
        sample = AlignedSample(**kwargs)
        assert sample.sample_id == "A01_20240214_S2"
        assert sample.zone_id == "A01"
        assert sample.label == 0.42

    def test_valid_sample_to_model_dict(self):
        kwargs = make_valid_sample_kwargs()
        sample = AlignedSample(**kwargs)
        d = sample.to_model_dict()
        assert set(d.keys()) == {"image", "sensor_seq", "weather_ctx", "modality_mask"}
        assert d["image"].shape == (4, 224, 224)


class TestImageValidation:
    def test_image_wrong_shape_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["image"] = torch.rand(3, 224, 224)
        with pytest.raises(ValueError, match="image.*shape.*\\(3, 224, 224\\)"):
            AlignedSample(**valid_sample_kwargs)

    def test_image_wrong_dtype_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["image"] = torch.randint(0, 255, (4, 224, 224))
        with pytest.raises(ValueError, match="image.*dtype.*float32"):
            AlignedSample(**valid_sample_kwargs)


class TestSensorValidation:
    def test_sensor_wrong_shape_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["sensor_seq"] = torch.rand(24, 8)
        with pytest.raises(ValueError, match="sensor_seq.*shape.*\\(24, 8\\)"):
            AlignedSample(**valid_sample_kwargs)

    def test_sensor_wrong_features_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["sensor_seq"] = torch.rand(48, 4)
        with pytest.raises(ValueError, match="sensor_seq.*shape.*\\(48, 4\\)"):
            AlignedSample(**valid_sample_kwargs)


class TestWeatherValidation:
    def test_weather_wrong_shape_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["weather_ctx"] = torch.rand(5)
        with pytest.raises(ValueError, match="weather_ctx.*shape.*\\(5,\\)"):
            AlignedSample(**valid_sample_kwargs)


class TestModalityMaskValidation:
    def test_mask_wrong_shape_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["modality_mask"] = torch.tensor([1.0, 1.0])
        with pytest.raises(ValueError, match="modality_mask.*shape.*\\(2,\\)"):
            AlignedSample(**valid_sample_kwargs)

    def test_mask_invalid_values_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["modality_mask"] = torch.tensor([1.0, 0.5, 0.0])
        with pytest.raises(ValueError, match="modality_mask.*\\{0.0, 1.0\\}"):
            AlignedSample(**valid_sample_kwargs)

    def test_mask_all_zero_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["modality_mask"] = torch.tensor([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="at least one modality"):
            AlignedSample(**valid_sample_kwargs)


class TestLabelValidation:
    def test_label_below_range_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["label"] = -0.1
        with pytest.raises(ValueError, match="label.*\\[0.0, 1.0\\]"):
            AlignedSample(**valid_sample_kwargs)

    def test_label_above_range_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["label"] = 1.1
        with pytest.raises(ValueError, match="label.*\\[0.0, 1.0\\]"):
            AlignedSample(**valid_sample_kwargs)

    def test_label_boundary_zero(self, valid_sample_kwargs):
        valid_sample_kwargs["label"] = 0.0
        sample = AlignedSample(**valid_sample_kwargs)
        assert sample.label == 0.0

    def test_label_boundary_one(self, valid_sample_kwargs):
        valid_sample_kwargs["label"] = 1.0
        sample = AlignedSample(**valid_sample_kwargs)
        assert sample.label == 1.0


class TestTimestampValidation:
    def test_naive_timestamp_rejected(self, valid_sample_kwargs):
        valid_sample_kwargs["timestamp"] = datetime(2024, 2, 14, 3, 21, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            AlignedSample(**valid_sample_kwargs)


class TestIdValidation:
    def test_sample_id_invalid_pattern(self, valid_sample_kwargs):
        valid_sample_kwargs["sample_id"] = "invalid_id"
        with pytest.raises(ValueError, match="sample_id.*does not match"):
            AlignedSample(**valid_sample_kwargs)

    def test_zone_id_invalid_pattern(self, valid_sample_kwargs):
        valid_sample_kwargs["zone_id"] = "ZZ"
        with pytest.raises(ValueError, match="zone_id.*does not match"):
            AlignedSample(**valid_sample_kwargs)


class TestSourceTraceValidation:
    def test_source_trace_missing_key(self, valid_sample_kwargs):
        del valid_sample_kwargs["source_trace"]["label_formula"]
        with pytest.raises(ValueError, match="source_trace.*missing.*label_formula"):
            AlignedSample(**valid_sample_kwargs)

    def test_source_trace_not_dict(self, valid_sample_kwargs):
        valid_sample_kwargs["source_trace"] = "not_a_dict"
        with pytest.raises(ValueError, match="source_trace.*expected dict"):
            AlignedSample(**valid_sample_kwargs)
