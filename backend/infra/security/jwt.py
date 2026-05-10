"""JWT + APIKey authentication for FastAPI endpoints.

JWT HS256 for web users, APIKey SHA-256 for IoT devices.
Uses FastAPI Depends pattern at service boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("agtech.security")
_bearer = HTTPBearer(auto_error=False)


def decode_jwt(
    token: str,
    secret: str,
    algorithm: str = "HS256",
    issuer: str | None = None,
    audience: str | None = None,
) -> dict:
    """Decode and validate JWT token. Raises on invalid/expired."""
    import jwt  # PyJWT -- deferred import to avoid hard dep in tests

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        from backend.core.errors import AgTechError, ErrorCode
        raise AgTechError(
            error_code=ErrorCode.AUTH_EXPIRED_TOKEN,
            message="Token has expired",
            status_code=401,
        )
    except jwt.InvalidTokenError:
        from backend.core.errors import AgTechError, ErrorCode
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_TOKEN,
            message="Invalid token",
            status_code=401,
        )
    return payload


def verify_api_key(provided_key: str, stored_hash: str, salt: str = "") -> bool:
    """Verify IoT API key against stored SHA-256 hash."""
    computed = hashlib.sha256(f"{salt}{provided_key}".encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


def decode_access_token(token: str) -> dict:
    from backend.core.config import get_settings

    settings = get_settings()
    return decode_jwt(
        token,
        settings.JWT_SECRET,
        settings.JWT_ALGORITHM,
        settings.JWT_ISSUER,
        settings.JWT_AUDIENCE,
    )


def require_role(*allowed_roles: str):
    """FastAPI dependency: reject requests without required role."""

    def _dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ):
        from backend.core.config import get_settings
        from backend.core.errors import AgTechError, ErrorCode

        settings = get_settings()
        if not settings.AUTH_REQUIRED:
            if settings.ENV not in {"development", "test"}:
                raise AgTechError(
                    error_code=ErrorCode.AUTH_INVALID_TOKEN,
                    message="Auth bypass is disabled outside development and test",
                    status_code=401,
                )
            bypass_role = settings.DEV_AUTH_BYPASS_ROLE
            logger.warning(
                "auth_bypass activated",
                extra={
                    "event": "auth_bypass",
                    "bypass_role": bypass_role,
                    "path": request.url.path,
                    "method": request.method,
                    "env": settings.ENV,
                },
            )
            payload = {"sub": "dev-bypass", "role": bypass_role}
            request.state.auth_context = payload
            return payload

        if credentials is None or credentials.scheme.lower() != "bearer":
            raise AgTechError(
                error_code=ErrorCode.AUTH_INVALID_TOKEN,
                message="Missing bearer token",
                status_code=401,
            )

        payload = decode_jwt(
            credentials.credentials,
            settings.JWT_SECRET,
            settings.JWT_ALGORITHM,
            settings.JWT_ISSUER,
            settings.JWT_AUDIENCE,
        )
        role = payload.get("role", "")
        if role not in allowed_roles:
            raise AgTechError(
                error_code=ErrorCode.AUTH_INSUFFICIENT_ROLE,
                message="Insufficient role",
                status_code=403,
            )

        request.state.auth_context = payload
        return payload

    return _dependency
