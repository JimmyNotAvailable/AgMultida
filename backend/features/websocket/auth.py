from __future__ import annotations

from fastapi import WebSocket

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode
from backend.core.security import decode_access_token


def extract_ws_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def is_allowed_ws_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    return origin in get_settings().CORS_ORIGINS


def authenticate_websocket(websocket: WebSocket) -> dict:
    settings = get_settings()
    if not settings.WS_REQUIRE_AUTH:
        return {"sub": "dev-ws-bypass", "role": "viewer"}
    token = extract_ws_token(websocket)
    if not token:
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_TOKEN,
            message="Missing bearer token",
            status_code=401,
        )
    payload = decode_access_token(token)
    if payload.get("role") not in {"viewer", "operator", "admin"}:
        raise AgTechError(
            error_code=ErrorCode.AUTH_INSUFFICIENT_ROLE,
            message="Insufficient role",
            status_code=403,
        )
    return payload


def parse_ws_zones(websocket: WebSocket) -> set[str]:
    zones = websocket.query_params.get("zones")
    if not zones:
        return set()
    return {zone.strip() for zone in zones.split(",") if zone.strip()}
