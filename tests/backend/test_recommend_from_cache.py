"""Recommend-from-cache tests.

Validates:
- Cache hit produces valid IrrigationDecision
- Cache miss returns 409 PREDICTION_CACHE_MISS
- Degraded prediction propagates to decision
- Alert emitted on recommendation creation
- Decision cache stores latest after recommend

Run: pytest tests/backend/test_recommend_from_cache.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from core.errors import AgTechError, ErrorCode
from core.schemas import ConfidenceFlag, IrrigationDecision, PredictResponse, RecAction, RecommendFromCacheRequest
from features.prediction.cache import PredictionCacheService
from features.recommendation.service import DecisionCacheService, RecommendationService


def make_prediction(**overrides) -> PredictResponse:
    data = {
        "zone_id": "A01",
        "timestamp": datetime(2026, 5, 10, 10, 15, tzinfo=timezone.utc),
        "stress_prob": 0.65,
        "uncertainty": 0.12,
        "confidence_flag": ConfidenceFlag.HIGH,
        "degraded_mode": False,
        "attention_weights": [0.4, 0.3, 0.3],
        "model_version": "v1.0.0",
        "latency_ms": 42.0,
    }
    data.update(overrides)
    return PredictResponse(**data)


class MockAlertService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create_for_recommendation(self, zone_id, decision, prediction, *, imagery_stale=False):
        self.calls.append({"zone_id": zone_id, "action": decision.action.value})
        return None


@pytest.mark.anyio
async def test_recommend_from_cache_hit_returns_valid_decision():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(make_prediction(), "live")

    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.1)
    result = await service.recommend_from_cache(req)

    assert isinstance(result, IrrigationDecision)
    assert result.action in {RecAction.LIGHT, RecAction.MODERATE, RecAction.HEAVY, RecAction.NO_IRRIGATION, RecAction.HOLD}
    assert result.volume_mm >= 0.0


@pytest.mark.anyio
async def test_recommend_from_cache_miss_raises_409():
    prediction_cache = PredictionCacheService()
    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01")

    with pytest.raises(AgTechError) as exc_info:
        await service.recommend_from_cache(req)

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == ErrorCode.PREDICTION_CACHE_MISS
    assert exc_info.value.details["zone_id"] == "A01"


@pytest.mark.anyio
async def test_recommend_from_cache_stores_decision_in_cache():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(make_prediction(), "live")

    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.1)
    await service.recommend_from_cache(req)

    cached = await decision_cache.get_latest("A01")
    assert cached is not None
    assert cached.zone_id == "A01"


@pytest.mark.anyio
async def test_recommend_from_cache_emits_alert():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(make_prediction(stress_prob=0.8), "live")

    decision_cache = DecisionCacheService()
    alert_service = MockAlertService()
    service = RecommendationService(prediction_cache, decision_cache, alert_service=alert_service)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.1)
    await service.recommend_from_cache(req)

    assert len(alert_service.calls) >= 1
    assert alert_service.calls[0]["zone_id"] == "A01"


@pytest.mark.anyio
async def test_recommend_from_cache_degraded_propagates():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(
        make_prediction(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW, uncertainty=0.25),
        "degraded",
    )

    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.1)
    result = await service.recommend_from_cache(req)

    assert result.require_ack is True


@pytest.mark.anyio
async def test_recommend_from_cache_high_uncertainty_produces_hold():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(
        make_prediction(uncertainty=0.35, confidence_flag=ConfidenceFlag.LOW),
        "live",
    )

    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.1)
    result = await service.recommend_from_cache(req)

    assert result.action == RecAction.HOLD
    assert "uncertainty" in result.reason or "degraded" in result.reason


@pytest.mark.anyio
async def test_recommend_from_cache_rain_override():
    prediction_cache = PredictionCacheService()
    await prediction_cache.store_success(make_prediction(stress_prob=0.8), "live")

    decision_cache = DecisionCacheService()
    service = RecommendationService(prediction_cache, decision_cache)

    req = RecommendFromCacheRequest(zone_id="A01", soil_moisture=22.0, rain_forecast_3h=0.2)
    result = await service.recommend_from_cache(req)

    assert result.action == RecAction.NO_IRRIGATION
    assert result.reason == "rain_override"
