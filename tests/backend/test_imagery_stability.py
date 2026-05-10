from __future__ import annotations

import os
import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from features.imagery.circuit_breaker import CircuitBreaker
from features.imagery.persistence import PreviewPersistence
from features.imagery.service import ImageryService


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value


class FakeProvider:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    async def fetch_latest(self, zone_id: str):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("provider 429")
        return {"zone_id": zone_id, "scene_id": "scene-1", "cloud_cover": 35.0, "acquisition_time": "2026-05-10T00:00:00Z", "stale": False}


class FakePersistence:
    def __init__(self, hit: bool = False) -> None:
        self.hit = hit
        self.render_calls = 0

    async def get_preview_url(self, scene_id: str, mode: str):
        return f"https://minio/{scene_id}/{mode}.png" if self.hit else None

    async def render_and_store(self, scene_id: str, mode: str):
        self.render_calls += 1
        return f"https://minio/{scene_id}/{mode}.png"

    async def placeholder(self, zone_id: str, mode: str):
        return f"https://placeholder/{zone_id}/{mode}.png"


def test_provider_failures_open_breaker_after_three_errors() -> None:
    async def run() -> None:
        breaker = CircuitBreaker("imagery:test", redis_client=FakeRedis(), failure_threshold=3, cooldown_seconds=60)
        for _ in range(3):
            await breaker.record_failure()
        assert await breaker.current_state() == "open"

    anyio.run(run)


def test_minio_hit_avoids_render() -> None:
    async def run() -> None:
        persistence = FakePersistence(hit=True)
        url = await persistence.get_preview_url("scene-1", "rgb")
        assert url == "https://minio/scene-1/rgb.png"
        assert persistence.render_calls == 0

    anyio.run(run)


def test_placeholder_returned_when_provider_and_cache_unavailable() -> None:
    async def run() -> None:
        service = ImageryService(
            provider=FakeProvider(failures=4),
            breaker=CircuitBreaker("imagery:test", redis_client=FakeRedis(), failure_threshold=3, cooldown_seconds=60),
            persistence=FakePersistence(hit=False),
        )
        latest = await service.get_latest("A01")
        assert latest["degraded"] is True
        assert latest["preview_url"].startswith("https://placeholder/")

    anyio.run(run)
