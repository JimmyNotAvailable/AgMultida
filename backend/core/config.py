"""Application settings loaded from environment variables.

Batch 2 artifact: provides get_settings() for security.py and other modules.
No hardcoded secrets. All sensitive values sourced from os.getenv with
explicit failure if missing in production (no silent empty-string fallback
for critical secrets).

No pydantic-settings dependency -- uses stdlib os.getenv + dataclass.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Immutable application settings. Loaded once, cached via lru_cache."""

    JWT_SECRET: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    JWT_ALGORITHM: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    JWT_EXPIRY_MINUTES: int = field(
        default_factory=lambda: int(os.getenv("JWT_EXPIRY_MINUTES", os.getenv("JWT_EXPIRE_MINUTES", "60"))),
    )
    JWT_ISSUER: str = field(default_factory=lambda: os.getenv("JWT_ISSUER", "agmultida"))
    JWT_AUDIENCE: str = field(default_factory=lambda: os.getenv("JWT_AUDIENCE", "agmultida-admin"))
    AUTH_REQUIRED: bool = field(
        default_factory=lambda: os.getenv("AUTH_REQUIRED", "true").lower() == "true",
    )
    ADMIN_RATE_LIMIT_COUNT: int = field(
        default_factory=lambda: int(os.getenv("ADMIN_RATE_LIMIT_COUNT", "60")),
    )
    ADMIN_RATE_LIMIT_WINDOW_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("ADMIN_RATE_LIMIT_WINDOW_SECONDS", "60")),
    )
    RATE_LIMIT_BACKEND: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_BACKEND", "memory"),
    )
    RATE_LIMIT_REDIS_URL: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_REDIS_URL", os.getenv("REDIS_URL", "")),
    )
    RATE_LIMIT_NAMESPACE: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_NAMESPACE", "agmultida"),
    )
    CORS_ORIGINS: tuple[str, ...] = field(
        default_factory=lambda: tuple(origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()),
    )
    ENABLE_HSTS: bool = field(
        default_factory=lambda: os.getenv("ENABLE_HSTS", "false").lower() == "true",
    )
    TRUSTED_HOSTS: tuple[str, ...] = field(
        default_factory=lambda: tuple(host.strip() for host in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()),
    )
    WS_REQUIRE_AUTH: bool = field(
        default_factory=lambda: os.getenv("WS_REQUIRE_AUTH", "true").lower() == "true",
    )
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    ENV: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    DB_CONNECT_TIMEOUT_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
    )
    DB_POOL_MIN_SIZE: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MIN_SIZE", "1")),
    )
    DB_POOL_MAX_SIZE: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MAX_SIZE", "4")),
    )

    GATEWAY_MODE: str = field(
        default_factory=lambda: os.getenv("GATEWAY_MODE", "stub"),
    )
    AI_SERVING_URL: str = field(
        default_factory=lambda: os.getenv("AI_SERVING_URL", "http://localhost:8001"),
    )
    AI_SERVING_TIMEOUT_MS: int = field(
        default_factory=lambda: int(os.getenv("AI_SERVING_TIMEOUT_MS", "500")),
    )
    INGESTION_SERVICE_URL: str = field(
        default_factory=lambda: os.getenv("INGESTION_SERVICE_URL", "http://localhost:8003"),
    )
    INGESTION_SERVICE_TIMEOUT_MS: int = field(
        default_factory=lambda: int(os.getenv("INGESTION_SERVICE_TIMEOUT_MS", "500")),
    )
    AI_SERVING_MODE: str = field(
        default_factory=lambda: os.getenv("AI_SERVING_MODE", "manifest"),
    )
    ONNX_MODEL_PATH: str = field(
        default_factory=lambda: os.getenv("ONNX_MODEL_PATH", "artifacts/model.onnx"),
    )
    CALIBRATOR_PATH: str = field(
        default_factory=lambda: os.getenv("CALIBRATOR_PATH", "artifacts/calibrator.json"),
    )
    MANIFEST_PATH: str = field(
        default_factory=lambda: os.getenv("MANIFEST_PATH", "data/processed_real/sample_manifest.csv"),
    )
    MODEL_VERSION: str = field(
        default_factory=lambda: os.getenv("MODEL_VERSION", "v1.0.0"),
    )
    INTERNAL_API_KEY: str = field(
        default_factory=lambda: os.getenv("INTERNAL_API_KEY", ""),
    )
    INTERNAL_API_KEY_HEADER: str = field(
        default_factory=lambda: os.getenv("INTERNAL_API_KEY_HEADER", "X-Internal-API-Key"),
    )
    AI_SERVING_STRICT_READY: bool = field(
        default_factory=lambda: os.getenv("AI_SERVING_STRICT_READY", "false").lower() == "true",
    )
    ALERT_TELEGRAM_ENABLED: bool = field(
        default_factory=lambda: os.getenv("ALERT_TELEGRAM_ENABLED", "false").lower() == "true",
    )
    TELEGRAM_BOT_TOKEN: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""),
    )
    TELEGRAM_CHAT_ID: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""),
    )
    TELEGRAM_API_BASE_URL: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org"),
    )
    TELEGRAM_CONSUMER_GROUP: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CONSUMER_GROUP", "alert-monitor"),
    )
    TELEGRAM_CONSUMER_NAME: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CONSUMER_NAME", "gateway-1"),
    )
    TELEGRAM_MAX_RETRIES: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_MAX_RETRIES", "3")),
    )
    TELEGRAM_BLOCK_MS: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_BLOCK_MS", "1000")),
    )
    TELEGRAM_BACKOFF_BASE_SECONDS: float = field(
        default_factory=lambda: float(os.getenv("TELEGRAM_BACKOFF_BASE_SECONDS", "1.0")),
    )
    WEATHER_API_BASE_URL: str = field(
        default_factory=lambda: os.getenv("WEATHER_API_BASE_URL", "https://api.open-meteo.com/v1"),
    )
    WEATHER_TIMEOUT_MS: int = field(
        default_factory=lambda: int(os.getenv("WEATHER_TIMEOUT_MS", "1500")),
    )
    WEATHER_CACHE_TTL_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "900")),
    )
    IMAGERY_TIMEOUT_MS: int = field(
        default_factory=lambda: int(os.getenv("IMAGERY_TIMEOUT_MS", "1500")),
    )
    IMAGERY_METADATA_CACHE_TTL_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("IMAGERY_METADATA_CACHE_TTL_SECONDS", "21600")),
    )
    ZONE_STATUS_CACHE_TTL_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("ZONE_STATUS_CACHE_TTL_SECONDS", "300")),
    )
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))
    DEV_AUTH_BYPASS_ROLE: str = field(
        default_factory=lambda: os.getenv("DEV_AUTH_BYPASS_ROLE", "viewer"),
    )
    ALLOW_STUBS: bool = field(
        default_factory=lambda: os.getenv("ALLOW_STUBS", "true").lower() == "true",
    )

    def __post_init__(self) -> None:
        if not self.JWT_SECRET:
            if self.ENV == "production":
                raise RuntimeError(
                    "JWT_SECRET must be set via environment variable in production"
                )
        if self.GATEWAY_MODE not in {"stub", "live"}:
            raise RuntimeError("GATEWAY_MODE must be 'stub' or 'live'")
        if self.RATE_LIMIT_BACKEND not in {"memory", "redis"}:
            raise RuntimeError("RATE_LIMIT_BACKEND must be 'memory' or 'redis'")
        if self.ENV == "production" and not self.AUTH_REQUIRED:
            raise RuntimeError("AUTH_REQUIRED must stay true in production")
        if self.ENV == "production" and self.ALLOW_STUBS:
            raise RuntimeError(
                "ALLOW_STUBS must be false in production"
            )
        if not self.ALLOW_STUBS and self.GATEWAY_MODE == "stub":
            raise RuntimeError(
                "GATEWAY_MODE=stub is not allowed when ALLOW_STUBS=false"
            )
        if self.ENV == "production" and not self.WS_REQUIRE_AUTH:
            raise RuntimeError("WS_REQUIRE_AUTH must stay true in production")
        if self.ENV == "production" and not self.ENABLE_HSTS:
            raise RuntimeError("ENABLE_HSTS must stay true in production")
        if self.ENV == "production":
            if not self.CORS_ORIGINS:
                raise RuntimeError("CORS_ORIGINS must be set in production")
            if any(origin == '*' for origin in self.CORS_ORIGINS):
                raise RuntimeError("CORS_ORIGINS must not contain '*' in production")
            if any(origin.startswith('http://') for origin in self.CORS_ORIGINS):
                raise RuntimeError("CORS_ORIGINS must use https in production")
        if self.ENV == "production" and self.RATE_LIMIT_BACKEND == "memory":
            raise RuntimeError("RATE_LIMIT_BACKEND must not be 'memory' in production")
        if self.RATE_LIMIT_BACKEND == "redis" and not self.RATE_LIMIT_REDIS_URL:
            raise RuntimeError("RATE_LIMIT_REDIS_URL must be set when RATE_LIMIT_BACKEND=redis")
        if self.ENV == "production" and not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL must be set in production")
        if self.DB_POOL_MIN_SIZE < 0:
            raise RuntimeError("DB_POOL_MIN_SIZE must be >= 0")
        if self.DB_POOL_MAX_SIZE < 1:
            raise RuntimeError("DB_POOL_MAX_SIZE must be >= 1")
        if self.DB_POOL_MIN_SIZE > self.DB_POOL_MAX_SIZE:
            raise RuntimeError("DB_POOL_MIN_SIZE must be <= DB_POOL_MAX_SIZE")
        if self.WEATHER_TIMEOUT_MS < 1:
            raise RuntimeError("WEATHER_TIMEOUT_MS must be >= 1")
        if self.IMAGERY_TIMEOUT_MS < 1:
            raise RuntimeError("IMAGERY_TIMEOUT_MS must be >= 1")
        if self.WEATHER_CACHE_TTL_SECONDS < 1:
            raise RuntimeError("WEATHER_CACHE_TTL_SECONDS must be >= 1")
        if self.IMAGERY_METADATA_CACHE_TTL_SECONDS < 1:
            raise RuntimeError("IMAGERY_METADATA_CACHE_TTL_SECONDS must be >= 1")
        if self.ZONE_STATUS_CACHE_TTL_SECONDS < 1:
            raise RuntimeError("ZONE_STATUS_CACHE_TTL_SECONDS must be >= 1")
        if not self.INTERNAL_API_KEY_HEADER:
            raise RuntimeError("INTERNAL_API_KEY_HEADER must be set")
        if not self.INTERNAL_API_KEY and (
            self.ENV == "production" or self.GATEWAY_MODE == "live"
        ):
            raise RuntimeError(
                "INTERNAL_API_KEY must be set when APP_ENV=production or GATEWAY_MODE=live"
            )
        if self.INTERNAL_API_KEY and len(self.INTERNAL_API_KEY) < 16 and self.ENV == "production":
            raise RuntimeError("INTERNAL_API_KEY must be at least 16 characters")
        valid_roles = {"viewer", "operator", "admin"}
        if self.DEV_AUTH_BYPASS_ROLE not in valid_roles:
            raise RuntimeError(
                f"DEV_AUTH_BYPASS_ROLE must be one of {sorted(valid_roles)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
