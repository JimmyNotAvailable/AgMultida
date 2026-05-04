"""Shared async HTTP client factory for internal service communication.

Provides a configured httpx.AsyncClient with timeout from config.
Connection pooling via httpx defaults (100 max, 10 keepalive).
No retry logic -- retry/circuit-breaker belongs at the caller layer.
"""
from __future__ import annotations

import httpx


def create_http_client(
    base_url: str,
    timeout_ms: int = 500,
) -> httpx.AsyncClient:
    """Create a configured async HTTP client for internal service calls.

    Args:
        base_url: Target service base URL (e.g. http://localhost:8001).
        timeout_ms: Request timeout in milliseconds. Converted to seconds
            internally because httpx uses float seconds.
    """
    timeout_s = timeout_ms / 1000.0
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_s, connect=5.0),
        headers={"Content-Type": "application/json"},
    )
