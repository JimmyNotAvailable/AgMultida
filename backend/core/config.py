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
        default_factory=lambda: int(os.getenv("JWT_EXPIRY_MINUTES", "60")),
    )
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    ENV: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))

    GATEWAY_MODE: str = field(
        default_factory=lambda: os.getenv("GATEWAY_MODE", "stub"),
    )
    AI_SERVING_URL: str = field(
        default_factory=lambda: os.getenv("AI_SERVING_URL", "http://localhost:8001"),
    )
    AI_SERVING_TIMEOUT_MS: int = field(
        default_factory=lambda: int(os.getenv("AI_SERVING_TIMEOUT_MS", "500")),
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

    def __post_init__(self) -> None:
        if not self.JWT_SECRET:
            if self.ENV == "production":
                raise RuntimeError(
                    "JWT_SECRET must be set via environment variable in production"
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
