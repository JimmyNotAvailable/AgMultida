from __future__ import annotations

import os
import sys
from pathlib import Path

import anyio
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from api_gateway.main import app
from core.schemas import ConfidenceFlag, IrrigationDecision, PredictResponse, RecAction
from features.alerts.service import AlertService
from tests.backend.auth_helpers import auth_headers


def make_prediction(zone_id: str = "A03") -> PredictResponse:
    return PredictResponse(
        zone_id=zone_id,
        timestamp="2026-04-29T03:35:11.963000Z",
        stress_prob=0.72,
        uncertainty=0.1,
        confidence_flag=ConfidenceFlag.HIGH,
        degraded_mode=False,
        attention_weights=[0.4, 0.3, 0.3],
        model_version="v1.0.0",
        latency_ms=20.0,
    )


def make_decision() -> IrrigationDecision:
    return IrrigationDecision(
        action=RecAction.MODERATE,
        volume_mm=12.0,
        require_ack=False,
        reason="critical_stress_low_moisture",
        degraded_mode=False,
        confidence_flag=ConfidenceFlag.HIGH,
    )


async def seed_alert(service: AlertService, zone_id: str = "A03") -> None:
    await service.create_for_recommendation(zone_id, make_decision(), make_prediction(zone_id))


def test_zone_alerts_returns_feed_contract():
    with TestClient(app) as client:
        service = AlertService()
        anyio.run(seed_alert, service)
        app.state.alert_service = service
        response = client.get("/v1/zones/A03/alerts", headers=auth_headers("viewer"))

    assert response.status_code == 200
    body = response.json()
    assert body["zone_id"] == "A03"
    assert body["alerts"][0]["severity"] == "moderate"
    assert body["alerts"][0]["source"] == "alert_lifecycle"
    assert body["alerts"][0]["acknowledged"] is False
    assert body["alerts"][0]["timestamp"]


def test_zone_alerts_returns_empty_array_when_no_alerts():
    with TestClient(app) as client:
        app.state.alert_service = AlertService()
        response = client.get("/v1/zones/A03/alerts", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert response.json()["alerts"] == []


def test_zone_alerts_filters_by_severity():
    with TestClient(app) as client:
        service = AlertService()
        anyio.run(seed_alert, service)
        app.state.alert_service = service
        response = client.get("/v1/zones/A03/alerts?severity=watch", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert response.json()["alerts"] == []


def test_zone_alerts_filters_by_acknowledged():
    with TestClient(app) as client:
        service = AlertService()
        anyio.run(seed_alert, service)
        app.state.alert_service = service
        response = client.get("/v1/zones/A03/alerts?acknowledged=true", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert response.json()["alerts"] == []


def test_zone_alerts_applies_limit():
    with TestClient(app) as client:
        service = AlertService()
        anyio.run(seed_alert, service)
        app.state.alert_service = service
        response = client.get("/v1/zones/A03/alerts?limit=1", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert len(response.json()["alerts"]) == 1


def test_zone_alerts_rejects_bad_severity():
    with TestClient(app) as client:
        response = client.get("/v1/zones/A03/alerts?severity=bad", headers=auth_headers("viewer"))

    assert response.status_code == 422


def test_zone_alerts_rejects_bad_limit():
    with TestClient(app) as client:
        response = client.get("/v1/zones/A03/alerts?limit=101", headers=auth_headers("viewer"))

    assert response.status_code == 422
