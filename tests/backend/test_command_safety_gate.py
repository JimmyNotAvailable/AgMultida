"""Command safety gate unit + integration tests.

Validates:
- No recent prediction -> 409 COMMAND_BLOCKED_NO_RECENT_PREDICTION
- High uncertainty (>0.30) -> 409 COMMAND_BLOCKED_HIGH_UNCERTAINTY
- Degraded without ack+note -> 409 COMMAND_BLOCKED_DEGRADED_PREDICTION
- Degraded with ack+note -> 200 PENDING
- Expired prediction -> 409 blocked
- Demo prediction in production env -> 409 blocked
- Normal prediction passes gate
- Boundary uncertainty (exactly 0.30) passes
- Error contract shape includes zone_id, trace_id, timestamp

Run: pytest tests/backend/test_command_safety_gate.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from core.config import Settings
from core.errors import AgTechError
from core.schemas import ConfidenceFlag, IrrigationCommandRequest, PredictResponse, RecAction
from features.commands.policy import COMMAND_UNCERTAINTY_THRESHOLD, evaluate_command_safety
from features.commands.service import CommandSafetyService
from features.prediction.cache import PredictionCacheEntry, PredictionCacheService


def make_prediction(**overrides) -> PredictResponse:
    data = {
        "zone_id": "A01",
        "timestamp": datetime(2026, 5, 10, 10, 15, tzinfo=timezone.utc),
        "stress_prob": 0.42,
        "uncertainty": 0.12,
        "confidence_flag": ConfidenceFlag.HIGH,
        "degraded_mode": False,
        "attention_weights": [0.4, 0.3, 0.3],
        "model_version": "v1.0.0",
        "latency_ms": 42.0,
    }
    data.update(overrides)
    return PredictResponse(**data)


def make_cache_entry(prediction: PredictResponse | None = None, source: str = "live", created_at: datetime | None = None) -> PredictionCacheEntry | None:
    if prediction is None:
        return None
    return PredictionCacheEntry(
        response=prediction,
        created_at=created_at or datetime.now(timezone.utc),
        source=source,
        trace_id=str(prediction.trace_id),
        model_version=prediction.model_version,
    )


def make_command_request(**overrides) -> IrrigationCommandRequest:
    data = {
        "zone_id": "A01",
        "action": RecAction.LIGHT,
        "volume_mm": 8.0,
        "source": "ai_recommendation",
    }
    data.update(overrides)
    return IrrigationCommandRequest(**data)


class TestEvaluateCommandSafetyPolicy:
    def test_no_prediction_blocks_command(self):
        allowed, error_code, message = evaluate_command_safety(
            None, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_NO_RECENT_PREDICTION"

    def test_high_uncertainty_blocks_command(self):
        entry = make_cache_entry(make_prediction(uncertainty=0.31, confidence_flag=ConfidenceFlag.LOW))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_HIGH_UNCERTAINTY"

    def test_boundary_uncertainty_passes(self):
        entry = make_cache_entry(make_prediction(uncertainty=0.30))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is True
        assert error_code is None

    def test_degraded_without_ack_blocks(self):
        entry = make_cache_entry(make_prediction(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_DEGRADED_PREDICTION"

    def test_degraded_with_ack_but_no_note_blocks(self):
        entry = make_cache_entry(make_prediction(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=True, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_DEGRADED_PREDICTION"

    def test_degraded_with_ack_and_note_passes(self):
        entry = make_cache_entry(make_prediction(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=True, has_operator_note=True,
        )
        assert allowed is True
        assert error_code is None

    def test_normal_prediction_passes(self):
        entry = make_cache_entry(make_prediction())
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is True

    def test_expired_prediction_blocks(self):
        entry = make_cache_entry(
            make_prediction(),
            created_at=datetime.now(timezone.utc) - timedelta(seconds=700),
        )
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_NO_RECENT_PREDICTION"

    def test_zone_mismatch_blocks(self):
        entry = make_cache_entry(make_prediction(zone_id="B07"))
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_NO_RECENT_PREDICTION"

    def test_demo_prediction_in_production_blocks(self):
        prediction = make_prediction()
        entry = make_cache_entry(prediction, source="demo")
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="production", ack_override=False, has_operator_note=False,
        )
        assert allowed is False
        assert error_code.value == "COMMAND_BLOCKED_DEGRADED_PREDICTION"

    def test_demo_prediction_in_development_passes(self):
        prediction = make_prediction()
        entry = make_cache_entry(prediction, source="demo")
        allowed, error_code, _ = evaluate_command_safety(
            entry, zone_id="A01", app_env="development", ack_override=False, has_operator_note=False,
        )
        assert allowed is True

    def test_uncertainty_threshold_constant(self):
        assert COMMAND_UNCERTAINTY_THRESHOLD == 0.30


class TestCommandSafetyServiceIntegration:
    @pytest.mark.anyio
    async def test_ensure_allowed_raises_agtech_error_with_correct_shape(self):
        cache = PredictionCacheService()
        settings = Settings(JWT_SECRET="test-secret-not-for-production", AUTH_REQUIRED=False)
        service = CommandSafetyService(cache, settings)
        req = make_command_request()

        with pytest.raises(AgTechError) as exc_info:
            await service.ensure_allowed(req, ack_override=False)

        err = exc_info.value
        assert err.status_code == 409
        assert err.error_code.value == "COMMAND_BLOCKED_NO_RECENT_PREDICTION"
        assert "zone_id" in err.details
        assert err.details["zone_id"] == "A01"
        assert "timestamp" in err.details

    @pytest.mark.anyio
    async def test_ensure_allowed_passes_with_valid_prediction(self):
        cache = PredictionCacheService()
        await cache.store_success(make_prediction(), "live")
        settings = Settings(JWT_SECRET="test-secret-not-for-production", AUTH_REQUIRED=False)
        service = CommandSafetyService(cache, settings)
        req = make_command_request()

        await service.ensure_allowed(req, ack_override=False)

    @pytest.mark.anyio
    async def test_error_details_include_uncertainty_and_degraded_mode(self):
        prediction = make_prediction(uncertainty=0.35, confidence_flag=ConfidenceFlag.LOW)
        cache = PredictionCacheService()
        await cache.store_success(prediction, "live")
        settings = Settings(JWT_SECRET="test-secret-not-for-production", AUTH_REQUIRED=False)
        service = CommandSafetyService(cache, settings)
        req = make_command_request()

        with pytest.raises(AgTechError) as exc_info:
            await service.ensure_allowed(req, ack_override=False)

        assert exc_info.value.details["uncertainty"] == 0.35
        assert exc_info.value.details["degraded_mode"] is False
        assert exc_info.value.details["ack_override"] is False
