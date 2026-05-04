"""JWT + APIKey authentication for FastAPI endpoints.

JWT HS256 for web users, APIKey SHA-256 for IoT devices.
Uses FastAPI Depends pattern at service boundary.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("agtech.security")


def decode_jwt(token: str, secret: str, algorithm: str = "HS256") -> dict:
    """Decode and validate JWT token. Raises on invalid/expired."""
    import jwt  # PyJWT -- deferred import to avoid hard dep in tests

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        from backend.core.errors import AgTechError, ErrorCode
        raise AgTechError(
            error_code=ErrorCode.AUTH_EXPIRED_TOKEN,
            message="Token has expired",
            status_code=401,
        )
    except jwt.InvalidTokenError as exc:
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
    return computed == stored_hash


def require_role(*allowed_roles: str):
    """FastAPI dependency: reject requests without required role.

    Usage: @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    def _dependency(token: str = None):
        if token is None:
            from backend.core.errors import AgTechError, ErrorCode
            raise AgTechError(
                error_code=ErrorCode.AUTH_INVALID_TOKEN,
                message="No token provided",
                status_code=401,
            )
        from backend.core.config import get_settings
        settings = get_settings()
        payload = decode_jwt(token, settings.JWT_SECRET, settings.JWT_ALGORITHM)
        role = payload.get("role", "")
        if role not in allowed_roles:
            from backend.core.errors import AgTechError, ErrorCode
            raise AgTechError(
                error_code=ErrorCode.AUTH_INSUFFICIENT_ROLE,
                message=f"Role '{role}' not in {allowed_roles}",
                status_code=403,
            )
        return payload
    return _dependency
