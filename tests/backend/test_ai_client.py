from __future__ import annotations

import sys
from pathlib import Path

import anyio
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from api_gateway.clients.ai_client import LiveAIClient
from core.config import get_settings
from api_gateway.main import app
from fastapi.testclient import TestClient
from core.errors import AgTechError
from core.schemas import PredictRequest


def test_live_ai_client_success_and_header_injection():
    async def run() -> None:
        seen_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(
                200,
                json={
                    "trace_id": "123e4567-e89b-12d3-a456-426614174000",
                    "zone_id": "A01",
                    "timestamp": "2026-04-29T03:35:11.963000Z",
                    "stress_prob": 0.5,
                    "uncertainty": 0.1,
                    "confidence_flag": "high",
                    "degraded_mode": False,
                    "attention_weights": [0.5, 0.5],
                    "model_version": "v1.0.0",
                    "explanation": [],
                    "latency_ms": 10.0,
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="secret-key")
            response = await client.predict(
                PredictRequest(zone_id="A01", timestamp="2026-04-29T03:35:11.963000Z")
            )
            assert response.zone_id == "A01"
            assert seen_headers["x-internal-api-key"] == "secret-key"

    anyio.run(run)


def test_live_ai_client_custom_header_injection():
    async def run() -> None:
        seen_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(
                200,
                json={
                    "trace_id": "123e4567-e89b-12d3-a456-426614174000",
                    "zone_id": "A01",
                    "timestamp": "2026-04-29T03:35:11.963000Z",
                    "stress_prob": 0.5,
                    "uncertainty": 0.1,
                    "confidence_flag": "high",
                    "degraded_mode": False,
                    "attention_weights": [0.5, 0.5],
                    "model_version": "v1.0.0",
                    "explanation": [],
                    "latency_ms": 10.0,
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="secret-key", header_name="X-Service-Auth")
            await client.predict(
                PredictRequest(zone_id="A01", timestamp="2026-04-29T03:35:11.963000Z")
            )
            assert seen_headers["x-service-auth"] == "secret-key"

    anyio.run(run)


def test_live_ai_client_omits_header_when_internal_key_unset():
    async def run() -> None:
        seen_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(
                200,
                json={
                    "trace_id": "123e4567-e89b-12d3-a456-426614174000",
                    "zone_id": "A01",
                    "timestamp": "2026-04-29T03:35:11.963000Z",
                    "stress_prob": 0.5,
                    "uncertainty": 0.1,
                    "confidence_flag": "high",
                    "degraded_mode": False,
                    "attention_weights": [0.5, 0.3, 0.2],
                    "model_version": "v1.0.0",
                    "explanation": [],
                    "latency_ms": 10.0,
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="")
            await client.predict(
                PredictRequest(zone_id="A01", timestamp="2026-04-29T03:35:11.963000Z")
            )
            assert "x-internal-api-key" not in seen_headers

    anyio.run(run)


def test_live_ai_client_ready_injects_internal_header_when_set():
    async def run() -> None:
        seen_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "readiness_error": None,
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="secret-key")
            await client.ready()
            assert seen_headers["x-internal-api-key"] == "secret-key"

    anyio.run(run)


def test_live_ai_client_ready_omits_internal_header_when_unset():
    async def run() -> None:
        seen_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update(request.headers)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "readiness_error": None,
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="")
            await client.ready()
            assert "x-internal-api-key" not in seen_headers

    anyio.run(run)


def test_live_ai_client_maps_upstream_500_to_inference_failed():
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"}, request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http)
            with pytest.raises(AgTechError) as exc_info:
                await client.predict(
                    PredictRequest(zone_id="A01", timestamp="2026-04-29T03:35:11.963000Z")
                )
            assert exc_info.value.error_code.value == "INFERENCE_FAILED"
            assert exc_info.value.details["upstream_status"] == 500

    anyio.run(run)


def test_live_ai_client_ready_maps_upstream_payload():
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "readiness_error": None,
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http, internal_api_key="secret-key")
            ready = await client.ready()
            assert ready["status"] == "ok"
            assert ready["model_loaded"] is True
            assert ready["manifest_loaded"] is True

    anyio.run(run)


def test_live_ai_client_ready_maps_transport_failure():
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http)
            ready = await client.ready()
            assert ready["status"] == "degraded"
            assert ready["upstream_last_error"] == "AI serving readiness probe failed"

    anyio.run(run)


def test_live_ai_client_ready_is_stub_for_stub_client():
    async def run() -> None:
        from api_gateway.clients.ai_client import StubAIClient

        ready = await StubAIClient().ready()
        assert ready == {"status": "stub"}

    anyio.run(run)


def test_live_ai_client_maps_invalid_success_payload_to_inference_failed():
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"}, request=request)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = LiveAIClient(http)
            with pytest.raises(AgTechError) as exc_info:
                await client.predict(
                    PredictRequest(zone_id="A01", timestamp="2026-04-29T03:35:11.963000Z")
                )
            assert exc_info.value.error_code.value == "INFERENCE_FAILED"
            assert exc_info.value.status_code == 502
            assert exc_info.value.details == {
                "service": "ai_serving",
                "reason": "invalid_response",
            }

    anyio.run(run)


def test_gateway_startup_rejects_invalid_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GATEWAY_MODE", "liv")
    monkeypatch.setenv("INTERNAL_API_KEY", "secret-key")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="GATEWAY_MODE must be 'stub' or 'live'"):
        with TestClient(app):
            pass
    get_settings.cache_clear()


def test_gateway_readyz_reports_degraded_when_live_ai_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GATEWAY_MODE", "live")
    monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
    monkeypatch.setenv("INTERNAL_API_KEY", "secret-key")
    get_settings.cache_clear()
    with TestClient(app) as client:
        class ReadyClient:
            async def ready(self):
                return {
                    "status": "degraded",
                    "model_loaded": None,
                    "manifest_loaded": None,
                    "upstream_last_error": "AI serving readiness probe failed",
                }

        app.state.ai_client = ReadyClient()
        app.state.gateway_mode = "live"
        resp = client.get("/v1/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["ai_serving"]["upstream_last_error"] == "Dependency unavailable"
    get_settings.cache_clear()


def test_gateway_readyz_reports_ok_when_live_ai_ready(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GATEWAY_MODE", "live")
    monkeypatch.setenv("AI_SERVING_URL", "http://ai-serving.test")
    monkeypatch.setenv("INTERNAL_API_KEY", "secret-key")
    get_settings.cache_clear()
    with TestClient(app) as client:
        class ReadyClient:
            async def ready(self):
                return {
                    "status": "ok",
                    "model_loaded": True,
                    "manifest_loaded": True,
                    "upstream_last_error": None,
                }

        app.state.ai_client = ReadyClient()
        app.state.gateway_mode = "live"
        resp = client.get("/v1/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["dependencies"]["ai_serving"]["status"] == "ok"
    get_settings.cache_clear()
