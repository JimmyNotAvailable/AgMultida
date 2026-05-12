from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_EXAMPLE = PROJECT_ROOT / '.env.example'


def test_production_requires_hsts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('JWT_SECRET', 'x' * 32)
    monkeypatch.setenv('INTERNAL_API_KEY', 'y' * 16)
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('WS_REQUIRE_AUTH', 'true')
    monkeypatch.setenv('RATE_LIMIT_BACKEND', 'redis')
    monkeypatch.setenv('RATE_LIMIT_REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('ENABLE_HSTS', 'false')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('ALLOW_STUBS', 'false')
    monkeypatch.setenv('GATEWAY_MODE', 'live')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='ENABLE_HSTS must stay true in production'):
        get_settings()
    get_settings.cache_clear()


def test_production_rejects_http_cors_origins(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('JWT_SECRET', 'x' * 32)
    monkeypatch.setenv('INTERNAL_API_KEY', 'y' * 16)
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('WS_REQUIRE_AUTH', 'true')
    monkeypatch.setenv('RATE_LIMIT_BACKEND', 'redis')
    monkeypatch.setenv('RATE_LIMIT_REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('ENABLE_HSTS', 'true')
    monkeypatch.setenv('CORS_ORIGINS', 'http://localhost:3000')
    monkeypatch.setenv('ALLOW_STUBS', 'false')
    monkeypatch.setenv('GATEWAY_MODE', 'live')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/agmultida')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='CORS_ORIGINS must use https in production'):
        get_settings()
    get_settings.cache_clear()


def test_internal_api_key_requires_minimum_length(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('GATEWAY_MODE', 'live')
    monkeypatch.setenv('JWT_SECRET', 'x' * 32)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost:5432/agmultida')
    monkeypatch.setenv('RATE_LIMIT_BACKEND', 'redis')
    monkeypatch.setenv('RATE_LIMIT_REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('ENABLE_HSTS', 'true')
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('WS_REQUIRE_AUTH', 'true')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('INTERNAL_API_KEY', 'short-key')
    monkeypatch.setenv('ALLOW_STUBS', 'false')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='INTERNAL_API_KEY must be at least 16 characters'):
        get_settings()
    get_settings.cache_clear()


def test_env_example_keeps_expected_auth_and_service_keys():
    content = ENV_EXAMPLE.read_text(encoding='utf-8')
    assignments = dict(re.findall(r'^([A-Z0-9_]+)=(.*)$', content, flags=re.MULTILINE))

    expected = {
        'JWT_SECRET': 'CHANGE_ME_TO_A_RANDOM_256BIT_SECRET',
        'JWT_EXPIRY_MINUTES': '30',
        'AUTH_REQUIRED': 'true',
        'WS_REQUIRE_AUTH': 'true',
        'ENABLE_HSTS': 'false',
        'TRUSTED_HOSTS': 'localhost,127.0.0.1,testserver',
        'INTERNAL_API_KEY': 'CHANGE_ME_INTERNAL_API_KEY',
        'INTERNAL_API_KEY_HEADER': 'X-Internal-API-Key',
        'RATE_LIMIT_BACKEND': 'memory',
        'RATE_LIMIT_REDIS_URL': 'redis://redis:6379/0',
        'ADMIN_RATE_LIMIT_COUNT': '60',
        'ADMIN_RATE_LIMIT_WINDOW_SECONDS': '60',
        'DATABASE_URL': 'postgresql://agtech:CHANGE_ME_DB_PASSWORD@localhost:5432/agtech',
        'AI_SERVING_URL': 'http://ai-serving:8001',
        'AI_SERVING_TIMEOUT_MS': '500',
        'INGESTION_SERVICE_URL': 'http://ingestion-service:8003',
        'INGESTION_SERVICE_TIMEOUT_MS': '500',
        'DECISION_ENGINE_URL': 'http://decision-engine:8002',
        'DECISION_ENGINE_TIMEOUT_MS': '500',
        'WEATHER_API_BASE_URL': 'https://api.open-meteo.com/v1',
        'WEATHER_TIMEOUT_MS': '1500',
        'WEATHER_CACHE_TTL_SECONDS': '900',
        'IMAGERY_TIMEOUT_MS': '1500',
        'IMAGERY_METADATA_CACHE_TTL_SECONDS': '21600',
        'ZONE_STATUS_CACHE_TTL_SECONDS': '300',
        'REDIS_URL': 'redis://redis:6379/0',
        'AI_SERVING_STRICT_READY': 'false',
        'ALLOW_STUBS': 'true',
        'DEV_AUTH_BYPASS_ROLE': 'viewer',
    }

    for key, value in expected.items():
        assert assignments[key] == value
        assert len(re.findall(rf'^{key}=.*$', content, flags=re.MULTILINE)) == 1

    assert 'JWT_EXPIRE_MINUTES' not in assignments
    assert 'copy to .env' in content.lower()
    assert 'never commit .env' in content.lower()
    assert 'For production, switch RATE_LIMIT_BACKEND=redis' in content
    assert 'real INTERNAL_API_KEY' in content
    assert content.endswith('\n')


def test_production_rejects_allow_stubs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('JWT_SECRET', 'x' * 32)
    monkeypatch.setenv('INTERNAL_API_KEY', 'y' * 16)
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('WS_REQUIRE_AUTH', 'true')
    monkeypatch.setenv('RATE_LIMIT_BACKEND', 'redis')
    monkeypatch.setenv('RATE_LIMIT_REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('ENABLE_HSTS', 'true')
    monkeypatch.setenv('CORS_ORIGINS', 'https://app.example.com')
    monkeypatch.setenv('ALLOW_STUBS', 'true')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='ALLOW_STUBS must be false in production'):
        get_settings()
    get_settings.cache_clear()


def test_stubs_disabled_rejects_stub_gateway(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('APP_ENV', 'staging')
    monkeypatch.setenv('ALLOW_STUBS', 'false')
    monkeypatch.setenv('GATEWAY_MODE', 'stub')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='GATEWAY_MODE=stub is not allowed when ALLOW_STUBS=false'):
        get_settings()
    get_settings.cache_clear()


def test_invalid_dev_bypass_role_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('DEV_AUTH_BYPASS_ROLE', 'superadmin')
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match='DEV_AUTH_BYPASS_ROLE must be one of'):
        get_settings()
    get_settings.cache_clear()
