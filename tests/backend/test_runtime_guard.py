"""Runtime guard tests.

Validates:
- Dev auth bypass grants access in development mode
- Production rejects missing JWT_SECRET
- Production rejects AUTH_REQUIRED=false
- Production rejects ALLOW_STUBS=true
- Stub mode disabled when ALLOW_STUBS=false
- Structured error response contract shape
- Error masking never leaks stacktraces
- WS_REQUIRE_AUTH enforced in production
- ENABLE_HSTS enforced in production

Run: pytest tests/backend/test_runtime_guard.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

from api_gateway.main import app
from core.config import Settings, get_settings
from core.errors import AgTechError, ErrorCode, ErrorResponse, mask_internal_exception
from tests.backend.auth_helpers import auth_headers


class TestDevAuthBypass:
    def test_dev_bypass_allows_unauthenticated_predict(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AUTH_REQUIRED", "false")
        get_settings.cache_clear()
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json={
                "zone_id": "A01",
                "timestamp": "2024-02-14T03:21:00Z",
            })
        assert resp.status_code == 200
        get_settings.cache_clear()

    def test_dev_bypass_allows_unauthenticated_zones(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AUTH_REQUIRED", "false")
        get_settings.cache_clear()
        with TestClient(app) as client:
            resp = client.get("/v1/zones")
        assert resp.status_code == 200
        get_settings.cache_clear()

    def test_auth_required_rejects_unauthenticated(self):
        get_settings.cache_clear()
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json={
                "zone_id": "A01",
                "timestamp": "2024-02-14T03:21:00Z",
            })
        assert resp.status_code == 401
        get_settings.cache_clear()

    def test_authenticated_request_works_with_valid_token(self):
        get_settings.cache_clear()
        with TestClient(app) as client:
            resp = client.post("/v1/predict", json={
                "zone_id": "A01",
                "timestamp": "2024-02-14T03:21:00Z",
            }, headers=auth_headers("operator"))
        assert resp.status_code == 200
        get_settings.cache_clear()


class TestProductionFailFast:
    def test_production_rejects_empty_jwt_secret(self):
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            Settings(ENV="production", JWT_SECRET="")

    def test_production_rejects_auth_disabled(self):
        with pytest.raises(RuntimeError, match="AUTH_REQUIRED"):
            Settings(
                ENV="production",
                JWT_SECRET="a-real-secret-key-here",
                AUTH_REQUIRED=False,
                ENABLE_HSTS=True,
                DATABASE_URL="postgresql://localhost/test",
                CORS_ORIGINS=("https://app.example.com",),
                RATE_LIMIT_BACKEND="redis",
                RATE_LIMIT_REDIS_URL="redis://localhost:6379",
                INTERNAL_API_KEY="secret-key-1234567890",
            )

    def test_production_rejects_allow_stubs(self):
        with pytest.raises(RuntimeError, match="ALLOW_STUBS"):
            Settings(
                ENV="production",
                JWT_SECRET="a-real-secret-key-here",
                ALLOW_STUBS=True,
                ENABLE_HSTS=True,
                DATABASE_URL="postgresql://localhost/test",
                CORS_ORIGINS=("https://app.example.com",),
                RATE_LIMIT_BACKEND="redis",
                RATE_LIMIT_REDIS_URL="redis://localhost:6379",
                INTERNAL_API_KEY="secret-key-1234567890",
            )

    def test_production_rejects_ws_auth_disabled(self):
        with pytest.raises(RuntimeError, match="WS_REQUIRE_AUTH"):
            Settings(
                ENV="production",
                JWT_SECRET="a-real-secret-key-here",
                WS_REQUIRE_AUTH=False,
                ALLOW_STUBS=False,
                GATEWAY_MODE="live",
                ENABLE_HSTS=True,
                DATABASE_URL="postgresql://localhost/test",
                CORS_ORIGINS=("https://app.example.com",),
                RATE_LIMIT_BACKEND="redis",
                RATE_LIMIT_REDIS_URL="redis://localhost:6379",
                INTERNAL_API_KEY="secret-key-1234567890",
            )

    def test_production_rejects_hsts_disabled(self):
        with pytest.raises(RuntimeError, match="ENABLE_HSTS"):
            Settings(
                ENV="production",
                JWT_SECRET="a-real-secret-key-here",
                ENABLE_HSTS=False,
                ALLOW_STUBS=False,
                GATEWAY_MODE="live",
                DATABASE_URL="postgresql://localhost/test",
                CORS_ORIGINS=("https://app.example.com",),
                RATE_LIMIT_BACKEND="redis",
                RATE_LIMIT_REDIS_URL="redis://localhost:6379",
                INTERNAL_API_KEY="secret-key-1234567890",
            )

    def test_stub_disabled_blocks_stub_gateway_mode(self):
        with pytest.raises(RuntimeError, match="GATEWAY_MODE=stub"):
            Settings(
                JWT_SECRET="test-secret-not-for-production",
                ALLOW_STUBS=False,
                GATEWAY_MODE="stub",
            )


class TestStructuredErrorContract:
    def test_agtech_error_to_response_shape(self):
        error = AgTechError(
            error_code=ErrorCode.COMMAND_BLOCKED_HIGH_UNCERTAINTY,
            message="Command blocked: prediction uncertainty exceeds safety threshold",
            details={"zone_id": "A01", "uncertainty": 0.35},
            status_code=409,
        )
        response = error.to_response()
        assert isinstance(response, ErrorResponse)
        assert response.error_code == ErrorCode.COMMAND_BLOCKED_HIGH_UNCERTAINTY
        assert response.message == "Command blocked: prediction uncertainty exceeds safety threshold"
        assert response.details["zone_id"] == "A01"
        assert response.trace_id is not None
        assert response.timestamp is not None

    def test_mask_internal_exception_hides_stacktrace(self):
        try:
            raise ValueError("sensitive internal detail")
        except ValueError as exc:
            response = mask_internal_exception(exc)

        assert response.error_code == ErrorCode.INTERNAL_ERROR
        assert "sensitive" not in response.message
        assert "internal detail" not in response.message
        assert "contact support" in response.message.lower() or "internal error" in response.message.lower()

    def test_error_response_never_leaks_through_api(self):
        get_settings.cache_clear()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/v1/predict", json={
                "zone_id": "invalid",
                "timestamp": "2024-02-14T03:21:00Z",
            }, headers=auth_headers("operator"))
        body = resp.text
        assert "Traceback" not in body
        assert "RuntimeError" not in body
        assert "ValueError" not in body
        get_settings.cache_clear()

    def test_error_codes_are_domain_specific_strings(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)
            assert code.value == code.value.upper()
            assert "_" in code.value or code.value.isalpha()


class TestDevAuthBypassRole:
    def test_default_bypass_role_is_viewer(self):
        settings = Settings(JWT_SECRET="test-secret", AUTH_REQUIRED=False)
        assert settings.DEV_AUTH_BYPASS_ROLE == "viewer"

    def test_invalid_bypass_role_rejected(self):
        with pytest.raises(RuntimeError, match="DEV_AUTH_BYPASS_ROLE"):
            Settings(JWT_SECRET="test-secret", DEV_AUTH_BYPASS_ROLE="superadmin")
