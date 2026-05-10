from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from api_gateway.main import app
from core.schemas import ConfidenceFlag, IrrigationDecision, PredictResponse, RecAction
from features.alerts.lifecycle import ALERT_STATUS_ACKNOWLEDGED
from features.alerts.service import AlertService
from tests.backend.auth_helpers import auth_headers


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}
        self.streams: dict[str, list[dict[str, str]]] = {}
        self.expirations: dict[str, int] = {}

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes[key] = {**self.hashes.get(key, {}), **mapping}

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes.get(key, {}).get(field)

    async def lpush(self, key: str, value: str) -> None:
        self.lists[key] = [value, *self.lists.get(key, [])]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return self.lists.get(key, [])[start: None if end == -1 else end + 1]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def xadd(self, key: str, fields: dict[str, str]) -> None:
        self.streams.setdefault(key, []).append(fields)


def make_prediction(**overrides) -> PredictResponse:
    data = {
        "zone_id": "A01",
        "timestamp": "2026-04-29T03:35:11.963000Z",
        "stress_prob": 0.72,
        "uncertainty": 0.1,
        "confidence_flag": ConfidenceFlag.HIGH,
        "degraded_mode": False,
        "attention_weights": [0.4, 0.3, 0.3],
        "model_version": "v1.0.0",
        "latency_ms": 20.0,
    }
    data.update(overrides)
    return PredictResponse(**data)


def make_decision(action: RecAction = RecAction.MODERATE, degraded_mode: bool = False) -> IrrigationDecision:
    return IrrigationDecision(
        action=action,
        volume_mm=12.0,
        require_ack=False,
        reason="critical_stress_low_moisture",
        degraded_mode=degraded_mode,
        confidence_flag=ConfidenceFlag.HIGH,
    )


def test_high_stress_low_moisture_creates_moderate_alert() -> None:
    async def run() -> None:
        service = AlertService()
        alert = await service.create_for_recommendation("A01", make_decision(), make_prediction())
        assert alert is not None
        assert alert.severity == "moderate"
        assert alert.rule_id == "irrigation_action"

    anyio.run(run)


def test_high_uncertainty_creates_watch_alert_with_review_flag() -> None:
    async def run() -> None:
        service = AlertService()
        alert = await service.create_for_recommendation(
            "A01",
            make_decision(RecAction.NO_IRRIGATION),
            make_prediction(uncertainty=0.31),
        )
        assert alert is not None
        assert alert.severity == "watch"
        assert alert.require_review is True

    anyio.run(run)


def test_duplicate_recommendation_same_time_bucket_returns_existing_alert() -> None:
    async def run() -> None:
        service = AlertService()
        first = await service.create_for_recommendation("A01", make_decision(), make_prediction())
        second = await service.create_for_recommendation("A01", make_decision(), make_prediction())
        assert first is not None
        assert second is not None
        assert second.alert_id == first.alert_id
        assert len(await service.list_zone_alerts("A01", limit=10)) == 1

    anyio.run(run)


def test_alert_redis_structures_and_stream_are_written() -> None:
    async def run() -> None:
        redis = FakeRedis()
        service = AlertService(redis_client=redis)
        alert = await service.create_for_recommendation("A01", make_decision(), make_prediction())
        assert alert is not None
        assert f"alert:{alert.alert_id}" in redis.hashes
        assert redis.lists["alerts:zone:A01:open"] == [alert.alert_id]
        assert redis.expirations["alerts:zone:A01:open"] > 0
        assert redis.streams["alerts:events"]

    anyio.run(run)


def test_ack_api_updates_status_and_conflicts_on_second_ack() -> None:
    async def make_alert(service: AlertService) -> str:
        alert = await service.create_for_recommendation("A01", make_decision(), make_prediction())
        assert alert is not None
        return alert.alert_id

    class Aggregate:
        async def invalidate(self, zone_id: str) -> None:
            return None

    with TestClient(app, raise_server_exceptions=False) as client:
        service = AlertService()
        alert_id = anyio.run(make_alert, service)
        app.state.alert_service = service
        app.state.zone_status_cache = SimpleNamespace(invalidate=lambda zone_id: None)
        app.state.zone_status_aggregate = Aggregate()
        first = client.post(f"/v1/alerts/{alert_id}/ack", headers=auth_headers("operator"))
        second = client.post(f"/v1/alerts/{alert_id}/ack", headers=auth_headers("operator"))
    assert first.status_code == 200
    assert first.json()["acknowledged"] is True
    assert ALERT_STATUS_ACKNOWLEDGED in first.json()["message"]
    assert second.status_code == 409


def test_zone_alerts_returns_empty_array_for_no_lifecycle_alerts() -> None:
    app.state.alert_service = AlertService()
    with TestClient(app) as client:
        response = client.get("/v1/zones/B07/alerts", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()["alerts"] == []


@pytest.mark.parametrize("action", [RecAction.LIGHT, RecAction.MODERATE, RecAction.HEAVY, RecAction.HOLD])
def test_any_non_no_irrigation_action_creates_alert(action: RecAction) -> None:
    async def run() -> None:
        service = AlertService()
        alert = await service.create_for_recommendation("A01", make_decision(action), make_prediction())
        assert alert is not None

    anyio.run(run)
