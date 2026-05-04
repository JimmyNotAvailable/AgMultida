"""Integration wiring tests for Batch 4.

Validates:
- Predict/recommend endpoints delegate to injected clients
- Stub mode backward compatibility
- Live decision client calls evaluate_decision correctly
- Degraded mode propagation through wired path
- Error masking on client failures
- Timeout error contract (INFERENCE_TIMEOUT)
- /v1/readyz returns dependency status
- /v1/healthz regression check

Run: pytest tests/backend/test_integration_wiring.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

from api_gateway.main import app
from api_gateway.clients.ai_client import AIClient, StubAIClient
from api_gateway.clients.decision_client import (
    DecisionClient,
    LiveDecisionClient,
    StubDecisionClient,
)
from core.schemas import (
    ConfidenceFlag,
    IrrigationDecision,
    PredictRequest,
    PredictResponse,
    RecAction,
    RecommendRequest,
)
from core.errors import AgTechError, ErrorCode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_PREDICT_PAYLOAD = {
    "zone_id": "A01",
    "timestamp": "2024-02-14T03:21:00Z",
}

VALID_RECOMMEND_PAYLOAD = {
    "zone_id": "A01",
    "stress_prob": 0.65,
    "uncertainty": 0.12,
    "soil_moisture": 22.0,
    "rain_forecast_3h": 0.1,
}


# ---------------------------------------------------------------------------
# Stub Mode Tests (backward compatibility)
# ---------------------------------------------------------------------------
class TestStubModeBackwardCompat:
    """Existing Batch 2 behavior must be preserved in stub mode."""

    def test_predict_with_stub_client(self):
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD)
            assert resp.status_code == 200
            data = resp.json()
            parsed = PredictResponse(**data)
            assert parsed.stress_prob == 0.35
            assert parsed.uncertainty == 0.12
            assert parsed.model_version == "v1.0.0-stub"
            assert parsed.degraded_mode is False

    def test_recommend_with_stub_client(self):
        with TestClient(app) as client:
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD)
            assert resp.status_code == 200
            parsed = IrrigationDecision(**resp.json())
            assert parsed.action == RecAction.LIGHT
            assert parsed.reason == "stub_early_watch"

    def test_predict_response_has_trace_id(self):
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD)
            assert "trace_id" in resp.json()

    def test_recommend_response_has_trace_id(self):
        with TestClient(app) as client:
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD)
            assert "trace_id" in resp.json()


# ---------------------------------------------------------------------------
# Live Decision Client Tests (in-process wiring)
# ---------------------------------------------------------------------------
class TestLiveDecisionClient:
    """LiveDecisionClient calls evaluate_decision() in-process."""

    def test_critical_stress_returns_heavy(self):
        client_obj = LiveDecisionClient()
        req = RecommendRequest(
            zone_id="A01",
            stress_prob=0.65,
            uncertainty=0.10,
            soil_moisture=22.0,
            rain_forecast_3h=0.1,
        )
        result = client_obj.recommend(req)
        assert result.action == RecAction.HEAVY
        assert result.reason == "critical_stress_low_moisture"

    def test_rain_override_returns_no_irrigation(self):
        client_obj = LiveDecisionClient()
        req = RecommendRequest(
            zone_id="A01",
            stress_prob=0.65,
            uncertainty=0.10,
            soil_moisture=22.0,
            rain_forecast_3h=0.50,
        )
        result = client_obj.recommend(req)
        assert result.action == RecAction.NO_IRRIGATION
        assert result.reason == "rain_override"

    def test_degraded_mode_propagation(self):
        """degraded_mode=True inflates uncertainty and triggers HOLD."""
        client_obj = LiveDecisionClient()
        req = RecommendRequest(
            zone_id="A01",
            stress_prob=0.65,
            uncertainty=0.25,
            degraded_mode=True,
            soil_moisture=22.0,
            rain_forecast_3h=0.1,
        )
        result = client_obj.recommend(req)
        assert result.action == RecAction.HOLD
        assert result.degraded_mode is True
        assert result.confidence_flag == ConfidenceFlag.LOW


# ---------------------------------------------------------------------------
# Wired Predict Path (with app.state override)
# ---------------------------------------------------------------------------
class TestWiredPredictPath:
    """Test predict endpoint with injected live-like client."""

    def test_predict_delegates_to_injected_client(self):
        """Custom client injected via app.state is called by endpoint."""
        mock_response = PredictResponse(
            zone_id="A01",
            timestamp="2024-02-14T03:21:00Z",
            stress_prob=0.99,
            uncertainty=0.01,
            confidence_flag=ConfidenceFlag.HIGH,
            degraded_mode=False,
            attention_weights=[1.0],
            model_version="v-custom-mock",
            latency_ms=1.0,
        )

        class MockAIClient:
            async def predict(self, req):
                return mock_response

        with TestClient(app) as client:
            app.state.ai_client = MockAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD)
            assert resp.status_code == 200
            assert resp.json()["stress_prob"] == 0.99
            assert resp.json()["model_version"] == "v-custom-mock"

    def test_predict_timeout_returns_inference_timeout(self):
        """Client timeout produces INFERENCE_TIMEOUT error, not 500."""

        class TimeoutAIClient:
            async def predict(self, req):
                raise AgTechError(
                    error_code=ErrorCode.INFERENCE_TIMEOUT,
                    message="AI serving did not respond within timeout",
                    status_code=504,
                    details={"service": "ai_serving"},
                )

        with TestClient(app) as client:
            app.state.ai_client = TimeoutAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD)
            assert resp.status_code == 504
            body = resp.json()
            assert body["error_code"] == "INFERENCE_TIMEOUT"
            assert "Traceback" not in str(body)

    def test_predict_error_masked(self):
        """Unexpected exceptions are masked, no stacktrace leakage."""

        class CrashingAIClient:
            async def predict(self, req):
                raise RuntimeError("unexpected internal failure")

        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.ai_client = CrashingAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD)
            assert resp.status_code == 500
            body = resp.json()
            assert body["error_code"] == "INTERNAL_ERROR"
            assert "unexpected internal failure" not in body["message"]


# ---------------------------------------------------------------------------
# Wired Recommend Path (with app.state override)
# ---------------------------------------------------------------------------
class TestWiredRecommendPath:
    """Test recommend endpoint with injected live decision client."""

    def test_recommend_with_live_decision_client(self):
        """LiveDecisionClient wired through endpoint returns correct action."""
        with TestClient(app) as client:
            app.state.decision_client = LiveDecisionClient()
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD)
            assert resp.status_code == 200
            parsed = IrrigationDecision(**resp.json())
            assert parsed.action == RecAction.HEAVY
            assert parsed.reason == "critical_stress_low_moisture"

    def test_recommend_degraded_propagation_through_endpoint(self):
        """degraded_mode propagates through full endpoint -> client -> engine."""
        with TestClient(app) as client:
            app.state.decision_client = LiveDecisionClient()
            payload = {
                "zone_id": "A01",
                "stress_prob": 0.65,
                "uncertainty": 0.25,
                "degraded_mode": True,
                "soil_moisture": 22.0,
                "rain_forecast_3h": 0.1,
            }
            resp = client.post("/v1/recommend", json=payload)
            assert resp.status_code == 200
            parsed = IrrigationDecision(**resp.json())
            assert parsed.action == RecAction.HOLD
            assert parsed.degraded_mode is True


# ---------------------------------------------------------------------------
# Readiness & Health
# ---------------------------------------------------------------------------
class TestReadinessAndHealth:
    def test_healthz_unchanged(self):
        """Regression: /v1/healthz still returns ok."""
        with TestClient(app) as client:
            resp = client.get("/v1/healthz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_readyz_stub_mode(self):
        """/v1/readyz returns stub dependency status."""
        with TestClient(app) as client:
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["mode"] == "stub"
            assert data["dependencies"]["ai_serving"]["status"] == "stub"
            assert data["dependencies"]["decision_engine"]["status"] == "stub"

    def test_readyz_has_dependency_map(self):
        with TestClient(app) as client:
            resp = client.get("/v1/readyz")
            data = resp.json()
            assert "ai_serving" in data["dependencies"]
            assert "decision_engine" in data["dependencies"]
