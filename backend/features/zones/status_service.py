from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from uuid import uuid4

from backend.core.schemas import ZoneStatusResponse
from backend.features.prediction.cache import PredictionCacheService
from backend.features.recommendation.service import DecisionCacheService

ZONE_STATUS_TTL_SECONDS = 60

logger = logging.getLogger("agmultida.zone_status")


@dataclass(frozen=True)
class ZoneStatusCacheEntry:
    status: ZoneStatusResponse
    expires_at: datetime


class ZoneStatusService:
    def __init__(
        self,
        prediction_cache: PredictionCacheService,
        decision_cache: DecisionCacheService,
        redis_client: object | None = None,
        namespace: str = "zone_status",
        ttl_seconds: int = ZONE_STATUS_TTL_SECONDS,
    ) -> None:
        self._prediction_cache = prediction_cache
        self._decision_cache = decision_cache
        self._redis_client = redis_client
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, ZoneStatusCacheEntry] = {}

    async def get_or_build(
        self,
        zone_id: str,
        build_base_status: Callable[[], Awaitable[ZoneStatusResponse]],
    ) -> ZoneStatusResponse:
        started = time.perf_counter()
        cached = await self._get(zone_id)
        if cached is not None:
            self._log_aggregated(zone_id, cached, "hit", started)
            return cached

        status = await build_base_status()
        prediction_entry = await self._prediction_cache.get_latest(zone_id)
        decision_entry = await self._decision_cache.get_latest(zone_id)
        updates = {"latest_prediction": None, "latest_decision": None}
        prediction_age_ms = None
        decision_age_ms = None
        if prediction_entry is not None:
            updates["latest_prediction"] = prediction_entry.response
            prediction_age_ms = _age_ms(prediction_entry.created_at)
        if decision_entry is not None:
            updates["latest_decision"] = decision_entry.decision
            decision_age_ms = _age_ms(decision_entry.created_at)
        status = status.model_copy(update=updates)
        await self._set(zone_id, status)
        self._log_aggregated(zone_id, status, "miss", started, prediction_age_ms, decision_age_ms)
        return status

    async def invalidate(self, zone_id: str) -> None:
        key = self._key(zone_id)
        self._entries.pop(key, None)
        if self._redis_client is None:
            return
        try:
            await self._redis_client.delete(key)
        except Exception:
            return

    async def _get(self, zone_id: str) -> ZoneStatusResponse | None:
        key = self._key(zone_id)
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > datetime.now(timezone.utc):
            return entry.status
        if entry is not None:
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
            status = ZoneStatusResponse.model_validate(payload)
        except Exception:
            return None
        self._set_memory(key, status)
        return status

    async def _set(self, zone_id: str, status: ZoneStatusResponse) -> None:
        key = self._key(zone_id)
        self._set_memory(key, status)
        if self._redis_client is None:
            return
        try:
            await self._redis_client.set(key, json.dumps(status.model_dump(mode="json"), separators=(",", ":")), ex=self._ttl_seconds)
        except Exception:
            return

    def _set_memory(self, key: str, status: ZoneStatusResponse) -> None:
        self._entries[key] = ZoneStatusCacheEntry(
            status=status,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds),
        )

    def _key(self, zone_id: str) -> str:
        return f"{self._namespace}:{zone_id}"

    def _log_aggregated(
        self,
        zone_id: str,
        status: ZoneStatusResponse,
        cache_status: str,
        started: float,
        prediction_age_ms: int | None = None,
        decision_age_ms: int | None = None,
    ) -> None:
        alerts = status.alerts or []
        logger.info(
            "zone_status_aggregated",
            extra={
                "event": "zone_status_aggregated",
                "zone_id": zone_id,
                "cache_status": cache_status,
                "prediction_age_ms": prediction_age_ms,
                "decision_age_ms": decision_age_ms,
                "alert_open_count": len([alert for alert in alerts if not alert.acknowledged]),
                "trace_id": str(uuid4()),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )


def _age_ms(created_at: datetime) -> int:
    normalized = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - normalized).total_seconds() * 1000)
