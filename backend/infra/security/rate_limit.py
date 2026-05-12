from __future__ import annotations

import time
from collections import deque
from typing import Awaitable, Callable, Protocol

from fastapi import Request

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode


class RateLimiterBackend(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        ...


class MemoryRateLimiterBackend:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}

    def reset(self) -> None:
        self._buckets.clear()

    async def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        now = time.time()
        bucket = self._buckets.setdefault(key, deque())

        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if not bucket:
            self._buckets.pop(key, None)
            bucket = self._buckets.setdefault(key, deque())

        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return retry_after

        bucket.append(now)
        return None


class RedisRateLimiterBackend:
    def __init__(self, redis_url: str, namespace: str) -> None:
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError('redis package is required when RATE_LIMIT_BACKEND=redis') from exc

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._namespace = namespace

    async def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        redis_key = f'{self._namespace}:rate-limit:{key}'
        current = await self._client.incr(redis_key)
        if current == 1:
            await self._client.expire(redis_key, window_seconds)
        if current > limit:
            ttl = await self._client.ttl(redis_key)
            return max(1, int(ttl if ttl > 0 else window_seconds))
        return None


_MEMORY_BACKEND = MemoryRateLimiterBackend()
_BACKEND: RateLimiterBackend | None = None
_BACKEND_SIGNATURE: tuple[str, str, str] | None = None


def reset_rate_limiter_backend() -> None:
    global _BACKEND, _BACKEND_SIGNATURE
    _MEMORY_BACKEND.reset()
    _BACKEND = None
    _BACKEND_SIGNATURE = None


def get_rate_limiter_backend() -> RateLimiterBackend:
    global _BACKEND, _BACKEND_SIGNATURE
    settings = get_settings()
    signature = (settings.RATE_LIMIT_BACKEND, settings.RATE_LIMIT_REDIS_URL, settings.RATE_LIMIT_NAMESPACE)
    if _BACKEND is not None and _BACKEND_SIGNATURE == signature:
        return _BACKEND

    if settings.RATE_LIMIT_BACKEND == 'redis':
        _BACKEND = RedisRateLimiterBackend(settings.RATE_LIMIT_REDIS_URL, settings.RATE_LIMIT_NAMESPACE)
    else:
        _MEMORY_BACKEND.reset()
        _BACKEND = _MEMORY_BACKEND
    _BACKEND_SIGNATURE = signature
    return _BACKEND


async def check_rate_limit(scope: str, identity: str) -> None:
    limit, window = _scope_limits(scope)
    key = f'{scope}:{identity}'
    retry_after = await get_rate_limiter_backend().hit(key, limit, window)

    if retry_after is not None:
        raise AgTechError(
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message='Rate limit exceeded',
            details={'scope': scope, 'retry_after_seconds': retry_after},
            status_code=429,
        )


def _scope_limits(scope: str) -> tuple[int, int]:
    settings = get_settings()
    if scope == 'predict':
        return settings.PREDICT_RATE_LIMIT_COUNT, settings.PREDICT_RATE_LIMIT_WINDOW_SECONDS
    if scope == 'recommend':
        return settings.RECOMMEND_RATE_LIMIT_COUNT, settings.RECOMMEND_RATE_LIMIT_WINDOW_SECONDS
    if scope == 'auth':
        return settings.AUTH_RATE_LIMIT_COUNT, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    return settings.ADMIN_RATE_LIMIT_COUNT, settings.ADMIN_RATE_LIMIT_WINDOW_SECONDS


def create_rate_limit_dependency(scope: str) -> Callable[[Request], Awaitable[None]]:
    async def _dependency(request: Request) -> None:
        identity = getattr(request.state, 'auth_context', {}).get('sub', 'anonymous')
        await check_rate_limit(scope, identity)

    return _dependency
