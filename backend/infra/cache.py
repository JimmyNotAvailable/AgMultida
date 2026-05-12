from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class MemoryCacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class TieredCache(Generic[T]):
    def __init__(
        self,
        namespace: str,
        ttl_seconds: int,
        redis_ttl_seconds: int | None = None,
        redis_client: object | None = None,
    ) -> None:
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds
        self._redis_ttl_seconds = redis_ttl_seconds or ttl_seconds
        self._redis_client = redis_client
        self._entries: dict[str, MemoryCacheEntry[T]] = {}

    async def get(self, key: str, decoder: Callable[[str], T] | None = None) -> T | None:
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > datetime.now(timezone.utc):
            return entry.value
        if entry is not None:
            self._entries.pop(key, None)

        if self._redis_client is None or decoder is None:
            return None

        raw = await self._redis_client.get(self._redis_key(key))
        if raw is None:
            return None
        value = decoder(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        self._set_memory(key, value)
        return value

    async def set(self, key: str, value: T, encoder: Callable[[T], str] | None = None) -> T:
        self._set_memory(key, value)
        if self._redis_client is not None and encoder is not None:
            await self._redis_client.set(self._redis_key(key), encoder(value), ex=self._redis_ttl_seconds)
        return value

    async def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)
        if self._redis_client is not None:
            await self._redis_client.delete(self._redis_key(key))

    def _set_memory(self, key: str, value: T) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)
        self._entries[key] = MemoryCacheEntry(value=value, expires_at=expires_at)

    def _redis_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"


def json_decoder(value: str) -> dict:
    return json.loads(value)


def json_encoder(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"))
