from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production-32b')

from backend.core.errors import AgTechError, ErrorCode
from backend.core.imagery import (
    MAX_CLOUD_COVER,
    build_preview_url,
    build_stac_search_payload,
    get_latest_zone_imagery,
    get_zone_imagery_history,
    parse_stac_item,
    score_scene,
    search_sentinel_scenes,
    select_scenes,
)


class DummyScene:
    def __init__(self, scene_id: str, acquisition_time: datetime, cloud_cover: float, coverage: float):
        self.scene_id = scene_id
        self.acquisition_time = acquisition_time
        self.cloud_cover = cloud_cover
        self.coverage = coverage
        self.rgb_url = None
        self.ndvi_url = None
        self.source = 'sentinel-2-l2a'


def build_row(*, zone_id: str = 'A01', scene_id: str = 'scene-1', fetched_hours_ago: int = 1, acquired_days_ago: int = 1) -> dict:
    now = datetime.now(timezone.utc)
    return {
        'zone_id': zone_id,
        'scene_id': scene_id,
        'acquisition_time': now - timedelta(days=acquired_days_ago),
        'cloud_cover': 8.5,
        'rgb_url': 'https://example.com/visual.tif',
        'ndvi_url': 'https://example.com/nir.tif',
        'source': 'sentinel-2-l2a',
        'fetched_at': now - timedelta(hours=fetched_hours_ago),
    }


@pytest.mark.anyio
async def test_get_latest_zone_imagery_uses_fresh_persisted_row(monkeypatch):
    row = build_row()

    async def fake_latest_row(zone_id: str):
        return row

    async def fail_search(zone_id: str, polygon: list[list[float]], limit: int = 1):
        raise AssertionError('search should not run for fresh cached row')

    monkeypatch.setattr('backend.features.imagery.stac.try_load_latest_scene_row', fake_latest_row)
    monkeypatch.setattr('backend.features.imagery.stac.fetch_and_persist_zone_imagery_history', fail_search)

    scene = await get_latest_zone_imagery('A01', [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]])

    assert scene.scene_id == 'scene-1'
    assert scene.stale is False


@pytest.mark.anyio
async def test_get_latest_zone_imagery_returns_stale_fallback_on_upstream_error(monkeypatch):
    row = build_row(fetched_hours_ago=8)

    async def fake_latest_row(zone_id: str):
        return row

    async def fail_search(zone_id: str, polygon: list[list[float]], limit: int = 1):
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message='Imagery service unavailable',
            status_code=502,
        )

    monkeypatch.setattr('backend.features.imagery.stac.try_load_latest_scene_row', fake_latest_row)
    monkeypatch.setattr('backend.features.imagery.stac.fetch_and_persist_zone_imagery_history', fail_search)

    scene = await get_latest_zone_imagery('A01', [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]])

    assert scene.scene_id == 'scene-1'
    assert scene.stale is True


@pytest.mark.anyio
async def test_get_zone_imagery_history_uses_fresh_persisted_rows(monkeypatch):
    rows = [build_row(scene_id='scene-1'), build_row(scene_id='scene-2', acquired_days_ago=2)]

    async def fake_history_rows(zone_id: str, limit: int):
        return rows[:limit]

    async def fail_fetch(zone_id: str, polygon: list[list[float]], limit: int = 10):
        raise AssertionError('refresh should not run for fresh history rows')

    monkeypatch.setattr('backend.features.imagery.stac.try_load_scene_history_rows', fake_history_rows)
    monkeypatch.setattr('backend.features.imagery.stac.fetch_and_persist_zone_imagery_history', fail_fetch)

    history = await get_zone_imagery_history('A01', [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]], limit=2)

    assert len(history.scenes) == 2
    assert history.scenes[0].scene_id == 'scene-1'
    assert history.scenes[1].scene_id == 'scene-2'


@pytest.mark.anyio
async def test_get_zone_imagery_history_returns_stale_rows_on_upstream_error(monkeypatch):
    rows = [build_row(scene_id='scene-1', fetched_hours_ago=8), build_row(scene_id='scene-2', fetched_hours_ago=8, acquired_days_ago=2)]

    async def fake_history_rows(zone_id: str, limit: int):
        return rows[:limit]

    async def fail_fetch(zone_id: str, polygon: list[list[float]], limit: int = 10):
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message='Imagery service unavailable',
            status_code=502,
        )

    monkeypatch.setattr('backend.features.imagery.stac.try_load_scene_history_rows', fake_history_rows)
    monkeypatch.setattr('backend.features.imagery.stac.fetch_and_persist_zone_imagery_history', fail_fetch)

    history = await get_zone_imagery_history('A01', [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]], limit=2)

    assert len(history.scenes) == 2
    assert all(scene.stale is True for scene in history.scenes)


@pytest.mark.anyio
async def test_get_latest_zone_imagery_raises_when_no_fallback_exists(monkeypatch):
    async def fake_latest_row(zone_id: str):
        return None

    async def fail_search(zone_id: str, polygon: list[list[float]], limit: int = 1):
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message='Imagery service unavailable',
            status_code=502,
        )

    monkeypatch.setattr('backend.features.imagery.stac.try_load_latest_scene_row', fake_latest_row)
    monkeypatch.setattr('backend.features.imagery.stac.fetch_and_persist_zone_imagery_history', fail_search)

    with pytest.raises(AgTechError) as exc_info:
        await get_latest_zone_imagery('A01', [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]])

    assert exc_info.value.error_code == ErrorCode.DEGRADED_SERVICE


def test_build_stac_search_payload_uses_polygon_and_cloud_limit():
    polygon = [[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]]

    payload = build_stac_search_payload(polygon, limit=7)

    assert payload['collections'] == ['sentinel-2-l2a']
    assert payload['intersects']['coordinates'] == [polygon]
    assert payload['limit'] == 7
    assert payload['query']['eo:cloud_cover']['lt'] == MAX_CLOUD_COVER


def test_parse_stac_item_extracts_scene_and_assets():
    item = {
        'id': 'scene-1',
        'properties': {
            'datetime': '2026-05-08T01:02:03Z',
            'eo:cloud_cover': 12.4,
            's2:valid_pixel_percentage': 92.0,
        },
        'assets': {
            'visual': {'href': 'https://example.com/visual.tif'},
            'nir': {'href': 'https://example.com/nir.tif'},
        },
    }

    parsed = parse_stac_item(item)

    assert parsed is not None
    assert parsed.scene_id == 'scene-1'
    assert parsed.cloud_cover == 12.4
    assert parsed.coverage == 0.92
    assert parsed.rgb_url == 'https://example.com/visual.tif'
    assert parsed.ndvi_url == 'https://example.com/nir.tif'


@pytest.mark.parametrize(
    ('cloud_cover', 'expected'),
    [
        (21.0, None),
        ('bad', None),
        (5.0, 'scene-1'),
    ],
)
def test_parse_stac_item_filters_invalid_cloud_cover(cloud_cover, expected):
    item = {
        'id': 'scene-1',
        'properties': {'datetime': '2026-05-08T01:02:03Z', 'eo:cloud_cover': cloud_cover},
        'assets': {},
    }

    parsed = parse_stac_item(item)

    assert (parsed.scene_id if parsed else None) == expected


def test_select_scenes_uses_weighted_score():
    now = datetime.now(timezone.utc)
    recent = DummyScene('recent', now - timedelta(days=2), 18.0, 0.95)
    balanced = DummyScene('balanced', now - timedelta(days=5), 4.0, 0.9)
    old = DummyScene('old', now - timedelta(days=20), 1.0, 1.0)

    selected = select_scenes([recent, balanced, old])

    assert [scene.scene_id for scene in selected] == ['balanced', 'old', 'recent']
    assert score_scene(balanced, now) > score_scene(recent, now)


def test_build_preview_url_returns_proxy_path():
    assert build_preview_url('S2A_A01_20260508', 'rgb') == '/v1/imagery/preview/S2A_A01_20260508?mode=rgb'
    assert build_preview_url('S2A_A01_20260508', 'ndvi') == '/v1/imagery/preview/S2A_A01_20260508?mode=ndvi'


@pytest.mark.anyio
async def test_search_sentinel_scenes_uses_imagery_timeout(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {'features': []}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured['timeout'] = kwargs['timeout']

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, path: str, json: dict):
            captured['path'] = path
            captured['payload'] = json
            return FakeResponse()

    class FakeSettings:
        IMAGERY_TIMEOUT_MS = 2345
        IMAGERY_METADATA_CACHE_TTL_SECONDS = 21600

    monkeypatch.setattr('backend.features.imagery.stac.httpx.AsyncClient', FakeClient)
    monkeypatch.setattr('backend.features.imagery.stac.get_settings', lambda: FakeSettings())

    await search_sentinel_scenes([[105.0, 10.0], [106.0, 10.0], [106.0, 11.0], [105.0, 10.0]], limit=3)

    assert captured['path'] == '/search'
    assert captured['payload']['limit'] == 3
    assert captured['timeout'].read == pytest.approx(2.345)
