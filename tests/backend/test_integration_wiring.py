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
- /v1/commands safety gate

Run: pytest tests/backend/test_integration_wiring.py -v
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

from backend.api_gateway.main import app
from tests.backend.auth_helpers import auth_headers
from backend.api_gateway.clients.ai_client import LiveAIClient
from backend.core.config import get_settings
from backend.api_gateway.clients.decision_client import LiveDecisionClient
from backend.core.schemas import ConfidenceFlag, IrrigationDecision, PredictResponse, RecAction, RecommendRequest
from backend.core.errors import AgTechError, ErrorCode

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

VALID_COMMAND_PAYLOAD = {
    "zone_id": "A01",
    "action": "light",
    "volume_mm": 8,
    "source": "ai_recommendation",
}

VALID_COMMAND_ACK_PAYLOAD = {
    "zone_id": "A01",
    "action": "light",
    "volume_mm": 8,
    "source": "ai_recommendation",
    "operator_note": "Reviewed degraded prediction",
}

VALID_COMMAND_MISSING_ACK_NOTE_PAYLOAD = {
    "zone_id": "A01",
    "action": "light",
    "volume_mm": 8,
    "source": "ai_recommendation",
    "operator_note": "",
}


def make_prediction_response(**overrides) -> PredictResponse:
    data = {
        "zone_id": "A01",
        "timestamp": "2024-02-14T03:21:00Z",
        "stress_prob": 0.65,
        "uncertainty": 0.12,
        "confidence_flag": ConfidenceFlag.HIGH,
        "degraded_mode": False,
        "attention_weights": [1.0],
        "model_version": "v-custom-mock",
        "latency_ms": 1.0,
    }
    data.update(overrides)
    return PredictResponse(**data)


class StaticPredictionEntry:
    def __init__(self, response: PredictResponse):
        self.response = response
        self.trace_id = str(response.trace_id)
        self.model_version = response.model_version
        self.source = 'live'
        self.created_at = datetime.now(timezone.utc)


class StaticPredictionCache:
    def __init__(self, entry: StaticPredictionEntry | None):
        self._entry = entry

    async def get_latest(self, zone_id: str):
        return self._entry


class NoopPredictionService:
    async def complete_prediction(self, req, prediction):
        return prediction


class NoopZoneStatusCache:
    def invalidate(self, zone_id: str):
        return None

    def get(self, zone_id: str):
        return None

    def set(self, zone_id: str, value):
        return value


class NoopAIClient:
    async def predict(self, req):
        return make_prediction_response()

    async def ready(self):
        return {'status': 'stub'}


class NoopDecisionClient:
    def recommend(self, req):
        return IrrigationDecision(action=RecAction.LIGHT, volume_mm=8.0, require_ack=False, reason='ok', degraded_mode=False, confidence_flag=ConfidenceFlag.HIGH)


def install_command_gate_state(prediction: PredictResponse | None):
    from backend.features.commands.service import CommandSafetyService
    from backend.features.recommendation.service import DecisionCacheService, RecommendationService

    settings = get_settings()
    app.state.ai_client = NoopAIClient()
    app.state.decision_client = NoopDecisionClient()
    app.state.prediction_service = NoopPredictionService()
    app.state.zone_status_cache = NoopZoneStatusCache()
    entry = None if prediction is None else StaticPredictionEntry(prediction)
    app.state.prediction_cache = StaticPredictionCache(entry)
    app.state.decision_cache = DecisionCacheService()
    app.state.recommendation_service = RecommendationService(app.state.prediction_cache, app.state.decision_cache)
    app.state.command_safety_service = CommandSafetyService(app.state.prediction_cache, settings)


# ---------------------------------------------------------------------------
# Stub Mode Tests (backward compatibility)
# ---------------------------------------------------------------------------
class TestStubModeBackwardCompat:
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


class TestLiveDecisionClient:
    def test_critical_stress_returns_heavy(self):
        client_obj = LiveDecisionClient()
        req = RecommendRequest(zone_id="A01", stress_prob=0.65, uncertainty=0.10, soil_moisture=22.0, rain_forecast_3h=0.1)
        result = client_obj.recommend(req)
        assert result.action == RecAction.HEAVY
        assert result.reason == "critical_stress_low_moisture"

    def test_degraded_mode_propagation(self):
        client_obj = LiveDecisionClient()
        req = RecommendRequest(zone_id="A01", stress_prob=0.65, uncertainty=0.25, degraded_mode=True, soil_moisture=22.0, rain_forecast_3h=0.1)
        result = client_obj.recommend(req)
        assert result.action == RecAction.HOLD
        assert result.degraded_mode is True
        assert result.confidence_flag == ConfidenceFlag.LOW


class TestWiredPredictPath:
    def test_predict_delegates_to_injected_client(self):
        mock_response = make_prediction_response(stress_prob=0.99, model_version="v-custom-mock")

        class MockAIClient:
            async def predict(self, req):
                return mock_response

        with TestClient(app) as client:
            app.state.ai_client = MockAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 200
            body = resp.json()
            assert body["stress_prob"] == 0.99
            assert body["model_version"] == "v-custom-mock"
            assert body["prediction_id"].startswith("pred_")

    def test_predict_rejects_upstream_zone_mismatch(self):
        mock_response = make_prediction_response(zone_id="A02")

        class MismatchAIClient:
            async def predict(self, req):
                return mock_response

        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.ai_client = MismatchAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 502
            assert resp.json()["details"]["reason"] == "response_mismatch"

    def test_predict_timeout_returns_inference_timeout(self):
        class TimeoutAIClient:
            async def predict(self, req):
                raise AgTechError(error_code=ErrorCode.INFERENCE_TIMEOUT, message="AI serving did not respond within timeout", status_code=504, details={"service": "ai_serving"})

        with TestClient(app) as client:
            app.state.ai_client = TimeoutAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 504
            assert resp.json()["error_code"] == "INFERENCE_TIMEOUT"

    def test_predict_error_masked(self):
        class CrashingAIClient:
            async def predict(self, req):
                raise RuntimeError("unexpected internal failure")

        with TestClient(app, raise_server_exceptions=False) as client:
            app.state.ai_client = CrashingAIClient()
            resp = client.post("/v1/predict", json=VALID_PREDICT_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 500
            assert resp.json()["error_code"] == "INTERNAL_ERROR"


class TestRecommendFromCache:
    def test_recommend_from_cache_success(self):
        with TestClient(app) as client:
            install_command_gate_state(make_prediction_response(stress_prob=0.5, uncertainty=0.1, degraded_mode=False))
            resp = client.post("/v1/recommend/from-cache", json={"zone_id": "A01", "soil_moisture": 22.0, "rain_forecast_3h": 0.1}, headers=auth_headers('operator'))
            assert resp.status_code == 200
            assert resp.json()["action"] in {"light", "moderate", "heavy", "no_irrigation", "hold"}

    def test_recommend_from_cache_miss_returns_409(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            install_command_gate_state(None)
            resp = client.post("/v1/recommend/from-cache", json={"zone_id": "A01"}, headers=auth_headers('operator'))
            assert resp.status_code == 409
            assert resp.json()["error_code"] == "PREDICTION_CACHE_MISS"


class TestCommandSafetyGate:
    def test_commands_block_when_prediction_missing(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            install_command_gate_state(None)
            resp = client.post("/v1/commands", json=VALID_COMMAND_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 409
            body = resp.json()
            assert body["error_code"] == "COMMAND_BLOCKED_NO_RECENT_PREDICTION"
            assert body["details"]["zone_id"] == "A01"

    def test_commands_block_when_prediction_uncertain(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            install_command_gate_state(make_prediction_response(uncertainty=0.31, confidence_flag=ConfidenceFlag.LOW))
            resp = client.post("/v1/commands", json=VALID_COMMAND_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 409
            assert resp.json()["error_code"] == "COMMAND_BLOCKED_HIGH_UNCERTAINTY"

    def test_commands_block_degraded_without_ack(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            install_command_gate_state(make_prediction_response(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW))
            resp = client.post("/v1/commands", json=VALID_COMMAND_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 409
            assert resp.json()["error_code"] == "COMMAND_BLOCKED_DEGRADED_PREDICTION"

    def test_commands_allow_degraded_with_ack(self):
        with TestClient(app) as client:
            install_command_gate_state(make_prediction_response(degraded_mode=True, confidence_flag=ConfidenceFlag.LOW, uncertainty=0.12))
            resp = client.post("/v1/commands?ack=true", json=VALID_COMMAND_ACK_PAYLOAD, headers=auth_headers('operator'))
            assert resp.status_code == 200
            assert resp.json()["status"] == "PENDING"


class TestReadinessAndHealth:
    def test_healthz_unchanged(self):
        with TestClient(app) as client:
            resp = client.get("/v1/healthz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_readyz_stub_mode(self):
        with TestClient(app) as client:
            resp = client.get("/v1/readyz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["mode"] == "stub"
            assert data["dependencies"]["ai_serving"]["status"] == "stub"

    def test_live_lifespan_wires_live_clients(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app):
            assert app.state.gateway_mode == "live"
            assert isinstance(app.state.ai_client, LiveAIClient)
        get_settings.cache_clear()

    def test_readyz_live_mode_does_not_expose_ai_serving_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GATEWAY_MODE", "live")
        monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
        monkeypatch.setenv("INTERNAL_API_KEY", "secret-key-123456")
        get_settings.cache_clear()
        with TestClient(app) as client:
            async def fake_ready():
                return {"status": "ok", "model_loaded": True, "manifest_loaded": True, "upstream_last_error": None}

            app.state.ai_client = SimpleNamespace(ready=fake_ready)
            app.state.gateway_mode = "live"
            resp = client.get("/v1/readyz")
            assert "url" not in resp.json()["dependencies"]["ai_serving"]
        get_settings.cache_clear()
