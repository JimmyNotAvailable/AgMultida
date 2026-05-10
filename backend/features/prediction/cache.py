from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.schemas import PredictResponse
from features.prediction.policy import PREDICTION_BUCKET_TTL_SECONDS, PREDICTION_LATEST_TTL_SECONDS, PREDICTION_MEMORY_TTL_SECONDS, prediction_timestamp_bucket


@dataclass(frozen=True)
class PredictionCacheEntry:
    response: PredictResponse
    created_at: datetime
    source: str
    trace_id: str
    model_version: str

    def to_payload(self) -> dict:
        return {
            "response": self.response.model_dump(mode="json"),
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "trace_id": self.trace_id,
            "model_version": self.model_version,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "PredictionCacheEntry":
        return cls(
            response=PredictResponse.model_validate(payload["response"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            source=payload["source"],
            trace_id=payload["trace_id"],
            model_version=payload["model_version"],
        )


@dataclass(frozen=True)
class MemoryEntry:
    value: PredictionCacheEntry
    expires_at: datetime


class PredictionCacheService:
    def __init__(self, redis_client: object | None = None, namespace: str = "pred") -> None:
        self._redis_client = redis_client
        self._namespace = namespace
        self._entries: dict[str, MemoryEntry] = {}

    async def store_success(self, prediction: PredictResponse, source: str) -> None:
        entry = PredictionCacheEntry(
            response=prediction,
            created_at=datetime.now(timezone.utc),
            source=source,
            trace_id=str(prediction.trace_id),
            model_version=prediction.model_version,
        )
        keys = [
            (self.latest_key(prediction.zone_id), PREDICTION_LATEST_TTL_SECONDS),
            (self.bucket_key(prediction.zone_id, prediction.timestamp.isoformat()), PREDICTION_BUCKET_TTL_SECONDS),
        ]
        for key, ttl_seconds in keys:
            self._set_memory(key, entry, min(ttl_seconds, PREDICTION_MEMORY_TTL_SECONDS))
            await self._set_redis(key, entry, ttl_seconds)

    async def get_latest(self, zone_id: str) -> PredictionCacheEntry | None:
        return await self._get(self.latest_key(zone_id))

    async def get_bucket(self, zone_id: str, timestamp: str) -> PredictionCacheEntry | None:
        return await self._get(self.bucket_key(zone_id, timestamp))

    def latest_key(self, zone_id: str) -> str:
        return f"{self._namespace}:{zone_id}:latest"

    def bucket_key(self, zone_id: str, timestamp: str) -> str:
        return f"{self._namespace}:{zone_id}:{prediction_timestamp_bucket(timestamp)}"

    async def _get(self, key: str) -> PredictionCacheEntry | None:
        memory = self._entries.get(key)
        if memory is not None and memory.expires_at > datetime.now(timezone.utc):
            return memory.value
        if memory is not None:
            self._entries.pop(key, None)

        if self._redis_client is None:
            return None

        try:
            raw = await self._redis_client.get(key)
        except Exception:
            return None
        if raw is None:
            return None
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            entry = PredictionCacheEntry.from_payload(payload)
        except Exception:
            await self._delete_redis(key)
            return None
        self._set_memory(key, entry, PREDICTION_MEMORY_TTL_SECONDS)
        return entry

    def _set_memory(self, key: str, entry: PredictionCacheEntry, ttl_seconds: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._entries[key] = MemoryEntry(value=entry, expires_at=expires_at)

    async def _set_redis(self, key: str, entry: PredictionCacheEntry, ttl_seconds: int) -> None:
        if self._redis_client is None:
            return
        try:
            await self._redis_client.set(key, json.dumps(entry.to_payload(), separators=(",", ":")), ex=ttl_seconds)
        except Exception:
            return

    async def _delete_redis(self, key: str) -> None:
        if self._redis_client is None:
            return
        try:
            await self._redis_client.delete(key)
        except Exception:
            return
