from __future__ import annotations

import json
from datetime import datetime, timezone

from features.imagery.circuit_breaker import CircuitBreaker
from features.imagery.persistence import PreviewPersistence
from features.imagery.schemas import ImageryMetadata


class ImageryService:
    def __init__(self, provider: object, breaker: CircuitBreaker, persistence: PreviewPersistence, redis_client: object | None = None, metadata_ttl_seconds: int = 900) -> None:
        self._provider = provider
        self._breaker = breaker
        self._persistence = persistence
        self._redis_client = redis_client
        self._metadata_ttl_seconds = metadata_ttl_seconds

    async def get_latest(self, zone_id: str) -> dict:
        cached = await self._get_cached(zone_id)
        if cached is not None:
            return cached
        if not await self._breaker.allow_request():
            return await self._placeholder(zone_id)
        try:
            raw = await self._provider.fetch_latest(zone_id)
        except Exception:
            await self._breaker.record_failure()
            return await self._placeholder(zone_id)
        await self._breaker.record_success()
        preview_url = await self._persistence.get_preview_url(raw['scene_id'], 'rgb')
        if preview_url is None:
            preview_url = await self._persistence.render_and_store(raw['scene_id'], 'rgb')
        payload = ImageryMetadata(
            zone_id=raw['zone_id'],
            scene_id=raw.get('scene_id'),
            cloud_cover=raw.get('cloud_cover'),
            acquisition_time=raw.get('acquisition_time'),
            stale=bool(raw.get('stale', False)),
            degraded=False,
            preview_url=preview_url,
        ).to_payload()
        await self._cache(zone_id, payload)
        return payload

    async def _placeholder(self, zone_id: str) -> dict:
        return ImageryMetadata(
            zone_id=zone_id,
            stale=True,
            degraded=True,
            preview_url=await self._persistence.placeholder(zone_id, 'rgb'),
            acquisition_time=datetime.now(timezone.utc).isoformat(),
        ).to_payload()

    async def _get_cached(self, zone_id: str) -> dict | None:
        if self._redis_client is None:
            return None
        raw = await self._redis_client.get(f'imagery:latest:{zone_id}')
        if not raw:
            return None
        return json.loads(raw)

    async def _cache(self, zone_id: str, payload: dict) -> None:
        if self._redis_client is None:
            return
        await self._redis_client.set(f'imagery:latest:{zone_id}', json.dumps(payload), ex=self._metadata_ttl_seconds)
