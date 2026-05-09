"""Contract tests for /v1/predict endpoint.

Validates that API gateway returns responses matching PredictResponse schema.
Uses FastAPI TestClient for synchronous testing without running the server.
Run: pytest tests/backend/test_predict_contract.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# JUN: Ensure backend root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

# Set required env var before importing config-dependent modules
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

from api_gateway.main import app
from tests.backend.auth_helpers import auth_headers
from core.schemas import PredictResponse, IrrigationDecision, HealthResponse


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestPredictEndpoint:
    def test_predict_returns_valid_schema(self, client):
        resp = client.post("/v1/predict", json={
            "zone_id": "A01",
            "timestamp": "2024-02-14T03:21:00Z",
        }, headers=auth_headers('operator'))
        assert resp.status_code == 200
        data = resp.json()
        parsed = PredictResponse(**data)
        assert 0.0 <= parsed.stress_prob <= 1.0
        assert parsed.trace_id is not None
        assert parsed.model_version is not None

    def test_predict_invalid_zone_rejected(self, client):
        resp = client.post("/v1/predict", json={
            "zone_id": "invalid",
            "timestamp": "2024-02-14T03:21:00Z",
        }, headers=auth_headers('operator'))
        assert resp.status_code == 422

    def test_predict_extra_fields_rejected(self, client):
        resp = client.post("/v1/predict", json={
            "zone_id": "A01",
            "timestamp": "2024-02-14T03:21:00Z",
            "injected_field": "attack",
        }, headers=auth_headers('operator'))
        assert resp.status_code == 422

    def test_predict_response_has_trace_id(self, client):
        resp = client.post("/v1/predict", json={
            "zone_id": "B07",
            "timestamp": "2024-06-01T12:00:00Z",
        }, headers=auth_headers('operator'))
        data = resp.json()
        assert "trace_id" in data
        assert data["trace_id"] is not None


class TestRecommendEndpoint:
    def test_recommend_returns_valid_schema(self, client):
        resp = client.post("/v1/recommend", json={
            "zone_id": "A01",
            "stress_prob": 0.65,
            "uncertainty": 0.12,
            "soil_moisture": 22.0,
            "rain_forecast_3h": 0.1,
        }, headers=auth_headers('operator'))
        assert resp.status_code == 200
        parsed = IrrigationDecision(**resp.json())
        assert parsed.action is not None


class TestHealthEndpoint:
    def test_healthz(self, client):
        resp = client.get("/v1/healthz")
        assert resp.status_code == 200
        parsed = HealthResponse(**resp.json())
        assert parsed.status == "ok"


class TestErrorContract:
    def test_no_stacktrace_in_error(self, client):
        resp = client.post("/v1/predict", json={
            "zone_id": "invalid",
            "timestamp": "2024-02-14T03:21:00Z",
        }, headers=auth_headers('operator'))
        body = resp.text
        assert "Traceback" not in body
        assert "File" not in body or "line" not in body.lower()
