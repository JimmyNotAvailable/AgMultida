from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'backend'))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production')

from api_gateway import main
from api_gateway.main import app
from core.imagery_proxy import build_preview_png, clear_preview_cache
from core.schemas import ImageryScene, ImagerySceneCollection
from tests.backend.auth_helpers import auth_headers


async def fake_latest(zone_id: str, polygon: list[list[float]]) -> ImageryScene:
    return ImageryScene(
        zone_id=zone_id,
        scene_id='S2A_A01_20260508',
        acquisition_time=datetime(2026, 5, 8, tzinfo=timezone.utc),
        cloud_cover=8.5,
        rgb_url='/v1/imagery/preview/S2A_A01_20260508?mode=rgb',
        ndvi_url='/v1/imagery/preview/S2A_A01_20260508?mode=ndvi',
        source='sentinel-2-l2a',
        stale=False,
    )


async def fake_history(zone_id: str, polygon: list[list[float]], limit: int = 10) -> ImagerySceneCollection:
    scene = await fake_latest(zone_id, polygon)
    return ImagerySceneCollection(zone_id=zone_id, scenes=[scene.model_copy() for _ in range(limit)])


async def fake_scene_for_preview(scene_id: str) -> ImageryScene | None:
    return ImageryScene(
        zone_id='A01',
        scene_id=scene_id,
        acquisition_time=datetime(2026, 5, 8, tzinfo=timezone.utc),
        cloud_cover=8.5,
        rgb_url='https://earth-search.aws.element84.com/visual.tif',
        ndvi_url='https://earth-search.aws.element84.com/nir.tif',
        source='sentinel-2-l2a',
        stale=False,
    )


class DummyPreview:
    def __init__(self, generated_from_source: bool = True):
        self.content = b'png'
        self.cache_key = 'preview-key'
        self.generated_from_source = generated_from_source


async def fake_build_preview_png(scene: ImageryScene, bbox: tuple[float, float, float, float], mode: str) -> DummyPreview:
    return DummyPreview(generated_from_source=True)


async def fake_build_preview_placeholder(scene: ImageryScene, bbox: tuple[float, float, float, float], mode: str) -> DummyPreview:
    return DummyPreview(generated_from_source=False)


def test_zone_imagery_latest_returns_scene(monkeypatch):
    monkeypatch.setattr(main, 'get_latest_zone_imagery_for_api', fake_latest)

    with TestClient(app) as client:
        response = client.get('/v1/zones/A01/imagery/latest', headers=auth_headers('viewer'))

    assert response.status_code == 200
    body = response.json()
    assert body['zone_id'] == 'A01'
    assert body['scene_id'] == 'S2A_A01_20260508'
    assert body['cloud_cover'] == 8.5
    assert body['rgb_url'] == '/v1/imagery/preview/S2A_A01_20260508?mode=rgb'
    assert body['ndvi_url'] == '/v1/imagery/preview/S2A_A01_20260508?mode=ndvi'
    assert body['stale'] is False


def test_zone_imagery_history_returns_limited_scenes(monkeypatch):
    monkeypatch.setattr(main, 'get_zone_imagery_history_for_api', fake_history)

    with TestClient(app) as client:
        response = client.get('/v1/zones/A01/imagery/history?limit=2', headers=auth_headers('viewer'))

    assert response.status_code == 200
    body = response.json()
    assert body['zone_id'] == 'A01'
    assert len(body['scenes']) == 2
    assert body['scenes'][0]['rgb_url'] == '/v1/imagery/preview/S2A_A01_20260508?mode=rgb'


def test_imagery_preview_uses_private_cache_headers(monkeypatch):
    monkeypatch.setattr(main, 'get_scene_for_preview', fake_scene_for_preview)
    monkeypatch.setattr(main, 'build_preview_png', fake_build_preview_png)

    with TestClient(app) as client:
        response = client.get('/v1/imagery/preview/S2A_A01_20260508?mode=rgb', headers=auth_headers('viewer'))

    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, max-age=86400'
    assert response.headers['vary'] == 'Authorization'
    assert response.headers['x-preview-source'] == 'rendered'
    assert response.headers['content-type'] == 'image/png'


def test_imagery_preview_marks_placeholder_source(monkeypatch):
    monkeypatch.setattr(main, 'get_scene_for_preview', fake_scene_for_preview)
    monkeypatch.setattr(main, 'build_preview_png', fake_build_preview_placeholder)

    with TestClient(app) as client:
        response = client.get('/v1/imagery/preview/S2A_A01_20260508?mode=rgb', headers=auth_headers('viewer'))

    assert response.status_code == 200
    assert response.headers['x-preview-source'] == 'placeholder'


def test_zone_imagery_latest_rejects_unknown_zone():
    with TestClient(app) as client:
        response = client.get('/v1/zones/Z99/imagery/latest', headers=auth_headers('viewer'))

    assert response.status_code == 404


def test_zone_imagery_history_rejects_bad_limit():
    with TestClient(app) as client:
        response = client.get('/v1/zones/A01/imagery/history?limit=11', headers=auth_headers('viewer'))

    assert response.status_code == 422


@pytest.mark.anyio
async def test_build_preview_png_falls_back_to_placeholder_for_unsafe_source():
    clear_preview_cache()
    scene = ImageryScene(
        zone_id='A01',
        scene_id='S2A_A01_20260508',
        acquisition_time=datetime(2026, 5, 8, tzinfo=timezone.utc),
        cloud_cover=8.5,
        rgb_url='/v1/imagery/preview/S2A_A01_20260508?mode=rgb',
        ndvi_url=None,
        source='sentinel-2-l2a',
        stale=False,
    )

    preview = await build_preview_png(scene, (105.0, 10.0, 106.0, 11.0), 'rgb')

    assert preview.generated_from_source is False
    assert preview.content.startswith(b'\x89PNG\r\n\x1a\n')
