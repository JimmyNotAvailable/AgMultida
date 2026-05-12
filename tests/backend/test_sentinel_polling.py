from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.core.schemas import ConfidenceFlag, ImageryScene, ImagerySceneCollection, IrrigationDecision, PredictResponse, RecAction, ZoneStatusResponse
from backend.features.imagery.polling import process_zone_imagery


class FakeAIClient:
    async def predict(self, req):
        return PredictResponse(
            zone_id=req.zone_id,
            timestamp=req.timestamp,
            stress_prob=0.64,
            uncertainty=0.12,
            confidence_flag=ConfidenceFlag.HIGH,
            degraded_mode=False,
            attention_weights=[0.4, 0.3, 0.3],
            model_version="test-model",
            latency_ms=12.0,
        )


class FakePredictionService:
    async def complete_prediction(self, req, prediction):
        return prediction.model_copy(update={"prediction_id": "pred_test"})


class FakeRecommendationService:
    def __init__(self) -> None:
        self.request = None

    async def recommend(self, req, trace_id=None):
        self.request = req
        return IrrigationDecision(
            action=RecAction.MODERATE,
            volume_mm=12.0,
            require_ack=False,
            reason="critical_stress_low_moisture",
            confidence_flag=ConfidenceFlag.HIGH,
        )


class FakeZoneStatusAggregate:
    def __init__(self) -> None:
        self.invalidated: list[str] = []

    async def get_or_build(self, zone_id, build_base_status):
        return ZoneStatusResponse(
            zone_id=zone_id,
            latest_telemetry={"soil_moisture": 21.0, "rain_3h": 8.0},
            weather={"hourly": {"precipitation_probability": [8, 6, 5]}},
            updated_at=datetime.now(timezone.utc),
        )

    async def invalidate(self, zone_id):
        self.invalidated.append(zone_id)


class FakeZoneStatusCache:
    def __init__(self) -> None:
        self.invalidated: list[str] = []

    def invalidate(self, zone_id):
        self.invalidated.append(zone_id)


@pytest.mark.anyio
async def test_process_zone_imagery_triggers_prediction_recommendation_and_ws(monkeypatch):
    published: list[tuple[str, str, dict]] = []
    scene = ImageryScene(
        zone_id="A01",
        scene_id="S2_A01",
        acquisition_time=datetime(2026, 5, 11, 4, 0, tzinfo=timezone.utc),
        cloud_cover=8.0,
        rgb_url="https://example.test/rgb.tif",
        ndvi_url="https://example.test/ndvi.tif",
        source="sentinel-2-l2a",
        stale=False,
    )

    async def fake_fetch_history(zone_id, polygon, limit=1):
        return ImagerySceneCollection(zone_id=zone_id, scenes=[scene])

    async def fake_publish(application, event, zone_id, payload):
        published.append((event, zone_id, payload))

    monkeypatch.setattr("backend.features.imagery.polling.load_zone_feature", lambda zone_id: {"geometry": {"coordinates": [[[105.0, 10.0], [106.0, 10.0], [105.0, 10.0]]]}})
    monkeypatch.setattr("backend.features.imagery.polling.fetch_and_persist_zone_imagery_history", fake_fetch_history)
    monkeypatch.setattr("backend.features.imagery.polling.publish_realtime_event", fake_publish)

    recommendation_service = FakeRecommendationService()
    aggregate = FakeZoneStatusAggregate()
    cache = FakeZoneStatusCache()
    app = SimpleNamespace(
        state=SimpleNamespace(
            ai_client=FakeAIClient(),
            prediction_service=FakePredictionService(),
            recommendation_service=recommendation_service,
            zone_status_aggregate=aggregate,
            zone_status_cache=cache,
            sentinel_processed_scenes={},
        )
    )

    await process_zone_imagery(app, "A01")
    await process_zone_imagery(app, "A01")

    assert recommendation_service.request is not None
    assert recommendation_service.request.zone_id == "A01"
    assert recommendation_service.request.soil_moisture == 21.0
    assert recommendation_service.request.rain_forecast_3h == 0.08
    assert cache.invalidated == ["A01"]
    assert aggregate.invalidated == ["A01"]
    assert published == [
        ("prediction_completed", "A01", {"zone_id": "A01", "prediction_id": "pred_test"}),
        ("recommendation_created", "A01", {"zone_id": "A01", "action": "moderate"}),
    ]


@pytest.mark.anyio
async def test_process_zone_imagery_skips_when_no_scene(monkeypatch):
    async def fake_fetch_history(zone_id, polygon, limit=1):
        return ImagerySceneCollection(zone_id=zone_id, scenes=[])

    monkeypatch.setattr("backend.features.imagery.polling.load_zone_feature", lambda zone_id: {"geometry": {"coordinates": [[]]}})
    monkeypatch.setattr("backend.features.imagery.polling.fetch_and_persist_zone_imagery_history", fake_fetch_history)
    app = SimpleNamespace(state=SimpleNamespace(ai_client=FakeAIClient()))

    await process_zone_imagery(app, "A01")
