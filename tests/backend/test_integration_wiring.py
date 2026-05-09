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
from types import SimpleNamespace

import httpx

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

from api_gateway.main import app
from tests.backend.auth_helpers import auth_headers
from api_gateway.clients.ai_client import AIClient, LiveAIClient, StubAIClient
from core.config import get_settings
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
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 200
            data = resp.json()
            parsed = PredictResponse(**data)
            assert parsed.stress_prob == 0.35
            assert parsed.uncertainty == 0.12
            assert parsed.model_version == "v1.0.0-stub"
            assert parsed.degraded_mode is False

    def test_recommend_with_stub_client(self):
        with TestClient(app) as client:
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 200
            parsed = IrrigationDecision(**resp.json())
            assert parsed.action == RecAction.LIGHT
            assert parsed.reason == "stub_early_watch"

    def test_predict_response_has_trace_id(self):
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert "trace_id" in resp.json()

    def test_recommend_response_has_trace_id(self):
        with TestClient(app) as client:
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD, headers=auth_headers('operator'))
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
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
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
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
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
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
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
            resp = client.post("/v1/recommend", json=VALID_RECOMMEND_PAYLOAD, headers=auth_headers('operator'))
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
            resp = client.post("/v1/recommend", json=payload, headers=auth_headers('operator'))
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
            assert data["dependencies"]["ai_serving"]["checked_at"]

    def test_readyz_has_dependency_map(self):
        with TestClient(app) as client:
            resp = client.get("/v1/readyz")
            data = resp.json()
            assert "ai_serving" in data["dependencies"]
            assert "decision_engine" in data["dependencies"]

    def test_live_lifespan_wires_live_clients(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app):
            assert app.state.gateway_mode == "live"
            assert isinstance(app.state.ai_client, LiveAIClient)
            assert isinstance(app.state.decision_client, LiveDecisionClient)
            assert app.state.ai_client._internal_headers == {"X-Internal-API-Key": "secret-key-123456"}
        get_settings.cache_clear()

    def test_live_lifespan_requires_internal_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="INTERNAL_API_KEY must be set"):
            with TestClient(app):
                pass
        get_settings.cache_clear()

    def test_stub_lifespan_allows_missing_internal_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "stub")
        monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
        get_settings.cache_clear()
        with TestClient(app):
            assert app.state.gateway_mode == "stub"
        get_settings.cache_clear()

    def test_live_lifespan_wires_custom_internal_header(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        monkeypatch.setenv("INTERNAL_API_KEY_HEADER", "X-Service-Auth")
        get_settings.cache_clear()
        with TestClient(app):
            assert app.state.ai_client._internal_headers == {"X-Service-Auth": "secret-key-123456"}
        get_settings.cache_clear()

    def test_readyz_live_mode_does_not_expose_ai_serving_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "upstream_last_error": None,
                }

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            data = resp.json()
            assert "url" not in data["dependencies"]["ai_serving"]
        get_settings.cache_clear()

    def test_readyz_stub_mode_keeps_stub_shape(self):
        with TestClient(app) as client:
            resp = client.get("/v1/readyz")
            data = resp.json()
            assert data["dependencies"]["ai_serving"]["status"] == "stub"
            assert "url" not in data["dependencies"]["ai_serving"]
            assert data["dependencies"]["ai_serving"]["checked_at"]

    def test_readyz_live_mode_uses_public_ready_method(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "upstream_last_error": None,
                }

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        get_settings.cache_clear()

    def test_readyz_live_mode_uses_public_ready_failure(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {
                    "status": "degraded",
                    "model_loaded": None,
                    "manifest_loaded": None,
                    "upstream_last_error": "AI serving readiness probe failed",
                }

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "degraded"
        get_settings.cache_clear()

    def test_readyz_live_mode_upstream_ready(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "upstream_last_error": None,
                }

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["dependencies"]["ai_serving"]["status"] == "ok"
            assert data["dependencies"]["ai_serving"]["model_loaded"] is True
            assert data["dependencies"]["ai_serving"]["manifest_loaded"] is True
            assert data["dependencies"]["ai_serving"]["checked_at"]
        get_settings.cache_clear()

    def test_readyz_live_mode_upstream_failure(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {
                    "status": "degraded",
                    "model_loaded": None,
                    "manifest_loaded": None,
                    "upstream_last_error": "AI serving readiness probe failed",
                }

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["dependencies"]["ai_serving"]["status"] == "degraded"
            assert data["dependencies"]["ai_serving"]["upstream_last_error"] == "Dependency unavailable"
            assert data["dependencies"]["ai_serving"]["checked_at"]
        get_settings.cache_clear()
