"""Shared async HTTP client factory for internal service communication.

Provides a configured httpx.AsyncClient with timeout from config.
Connection pooling via httpx defaults (100 max, 10 keepalive).
Retry helpers live here so external connectors handle 429s consistently.
"""
from __future__ import annotations

import asyncio

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
        timeout=httpx.Timeout(timeout_s, connect=timeout_s),
        headers={"Content-Type": "application/json"},
    )


def _retry_delay(response: httpx.Response, fallback: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return fallback
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        return fallback


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs: object,
) -> httpx.Response:
    """Send a request with exponential backoff and 429 Retry-After support."""
    attempts = max(max_retries, 1)
    last_error: httpx.HTTPError | None = None
    for attempt in range(attempts):
        try:
            if hasattr(client, "request"):
                response = await client.request(method, url, **kwargs)
            else:
                response = await getattr(client, method.lower())(url, **kwargs)
            if getattr(response, "status_code", None) == 429 and attempt < attempts - 1:
                await asyncio.sleep(_retry_delay(response, base_delay * (2**attempt)))
                continue
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2**attempt))
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2**attempt))
    raise last_error or httpx.HTTPError("Max retries exceeded")
