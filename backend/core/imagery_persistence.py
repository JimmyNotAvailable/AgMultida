from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.db import execute, fetch_all, fetch_one
from core.schemas import ImageryScene, ImagerySceneCollection

SCENE_COLUMNS = 'zone_id, scene_id, acquisition_time, cloud_cover, rgb_url, ndvi_url, source, fetched_at'


def scene_from_row(row: dict[str, Any], *, stale: bool = False) -> ImageryScene:
    payload = {key: value for key, value in row.items() if key != 'fetched_at'}
    return ImageryScene.model_validate({**payload, 'stale': stale})


def fetched_at_from_row(row: dict[str, Any]) -> datetime | None:
    fetched_at = row.get('fetched_at')
    return fetched_at if isinstance(fetched_at, datetime) else None


async def load_latest_scene(zone_id: str) -> ImageryScene | None:
    row = await load_latest_scene_row(zone_id)
    return scene_from_row(row) if row else None


async def load_latest_scene_row(zone_id: str) -> dict[str, Any] | None:
    return await fetch_one(
        f'''
        SELECT {SCENE_COLUMNS}
        FROM zone_imagery
        WHERE zone_id = %s
        ORDER BY acquisition_time DESC
        LIMIT 1
        ''',
        (zone_id,),
    )


async def load_scene(scene_id: str) -> ImageryScene | None:
    row = await fetch_one(
        f'''
        SELECT {SCENE_COLUMNS}
        FROM zone_imagery
        WHERE scene_id = %s
        ''',
        (scene_id,),
    )
    return scene_from_row(row) if row else None


async def load_scene_history(zone_id: str, limit: int) -> ImagerySceneCollection:
    rows = await load_scene_history_rows(zone_id, limit)
    return ImagerySceneCollection(zone_id=zone_id, scenes=[scene_from_row(row) for row in rows])


async def load_scene_history_rows(zone_id: str, limit: int) -> list[dict[str, Any]]:
    return await fetch_all(
        f'''
        SELECT {SCENE_COLUMNS}
        FROM zone_imagery
        WHERE zone_id = %s
        ORDER BY acquisition_time DESC
        LIMIT %s
        ''',
        (zone_id, limit),
    )


async def save_scene(scene: ImageryScene, metadata: dict[str, Any] | None = None) -> None:
    await execute(
        '''
        INSERT INTO zone_imagery (scene_id, zone_id, acquisition_time, cloud_cover, rgb_url, ndvi_url, source, metadata, fetched_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, now(), now())
        ON CONFLICT (scene_id) DO UPDATE
        SET zone_id = EXCLUDED.zone_id,
            acquisition_time = EXCLUDED.acquisition_time,
            cloud_cover = EXCLUDED.cloud_cover,
            rgb_url = EXCLUDED.rgb_url,
            ndvi_url = EXCLUDED.ndvi_url,
            source = EXCLUDED.source,
            metadata = EXCLUDED.metadata,
            fetched_at = now(),
            updated_at = now()
        ''',
        (
            scene.scene_id,
            scene.zone_id,
            scene.acquisition_time,
            scene.cloud_cover,
            scene.rgb_url,
            scene.ndvi_url,
            scene.source,
            json.dumps(metadata or {}),
        ),
    )
