from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from api_gateway.main import app
from tests.backend.auth_helpers import auth_headers


def test_zone_alerts_returns_feed_contract():
    with TestClient(app) as client:
        response = client.get("/v1/zones/A03/alerts", headers=auth_headers("viewer"))

    assert response.status_code == 200
    body = response.json()
    assert body["zone_id"] == "A03"
    assert body["alerts"][0]["severity"] == "critical"
    assert body["alerts"][0]["source"] == "alert_engine"
    assert body["alerts"][0]["acknowledged"] is False
    assert body["alerts"][0]["timestamp"]


def test_zone_alerts_filters_by_severity():
    with TestClient(app) as client:
        response = client.get("/v1/zones/A03/alerts?severity=warning", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert response.json()["alerts"] == []


def test_zone_alerts_filters_by_acknowledged():
    with TestClient(app) as client:
        response = client.get("/v1/zones/A03/alerts?acknowledged=true", headers=auth_headers("viewer"))

    assert response.status_code == 200
    assert response.json()["alerts"] == []


def test_zone_alerts_applies_limit():
    with TestClient(app) as client:
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
