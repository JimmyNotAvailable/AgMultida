from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.schemas import ZoneStatusResponse


@dataclass(frozen=True)
class CacheEntry:
    value: ZoneStatusResponse
    expires_at: datetime


class InMemoryZoneStatusCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, CacheEntry] = {}

    def get(self, zone_id: str) -> ZoneStatusResponse | None:
        entry = self._entries.get(zone_id)
        if entry is None:
            return None
        if entry.expires_at <= datetime.now(timezone.utc):
            self._entries.pop(zone_id, None)
            return None
        return entry.value

    def set(self, zone_id: str, value: ZoneStatusResponse) -> ZoneStatusResponse:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds)
        self._entries[zone_id] = CacheEntry(value=value, expires_at=expires_at)
        return value

    def invalidate(self, zone_id: str) -> None:
        self._entries.pop(zone_id, None)
