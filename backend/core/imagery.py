from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from core.config import get_settings
from core.errors import AgTechError, ErrorCode
from core.imagery_persistence import (
    fetched_at_from_row,
    load_latest_scene,
    load_latest_scene_row,
    load_scene,
    load_scene_history,
    load_scene_history_rows,
    save_scene,
    scene_from_row,
)
from core.schemas import ImageryScene, ImagerySceneCollection

EARTH_SEARCH_BASE_URL = "https://earth-search.aws.element84.com/v1"
SENTINEL_COLLECTION = "sentinel-2-l2a"
MAX_CLOUD_COVER = 20.0
HISTORY_LIMIT = 10
PREVIEW_BASE_PATH = "/v1/imagery/preview"
STALE_SCENE_AGE_DAYS = 7


@dataclass(frozen=True)
class SceneCandidate:
    scene_id: str
    acquisition_time: datetime
    cloud_cover: float
    coverage: float
    rgb_url: str | None
    ndvi_url: str | None
    source: str


async def get_latest_zone_imagery(zone_id: str, polygon: list[list[float]]) -> ImageryScene:
    persisted_row = await try_load_latest_scene_row(zone_id)
    if is_metadata_row_fresh(persisted_row):
        return scene_from_row(persisted_row, stale=is_scene_old(persisted_row['acquisition_time']))

    try:
        history = await fetch_and_persist_zone_imagery_history(zone_id, polygon, limit=1)
    except AgTechError:
        if persisted_row is not None:
            return scene_from_row(persisted_row, stale=True)
        raise

    if history.scenes:
        return history.scenes[0]
    if persisted_row is not None:
        return scene_from_row(persisted_row, stale=True)
    return build_stale_scene(zone_id)


async def get_zone_imagery_history(zone_id: str, polygon: list[list[float]], limit: int = HISTORY_LIMIT) -> ImagerySceneCollection:
    persisted_rows = await try_load_scene_history_rows(zone_id, limit)
    if are_history_rows_fresh(persisted_rows, limit):
        return ImagerySceneCollection(
            zone_id=zone_id,
            scenes=[scene_from_row(row, stale=is_scene_old(row['acquisition_time'])) for row in persisted_rows[:limit]],
        )

    try:
        return await fetch_and_persist_zone_imagery_history(zone_id, polygon, limit=limit)
    except AgTechError:
        if persisted_rows:
            return ImagerySceneCollection(zone_id=zone_id, scenes=[scene_from_row(row, stale=True) for row in persisted_rows[:limit]])
        raise


async def fetch_and_persist_zone_imagery_history(
    zone_id: str,
    polygon: list[list[float]],
    limit: int = HISTORY_LIMIT,
) -> ImagerySceneCollection:
    candidates = await search_sentinel_scenes(polygon, limit=max(limit, HISTORY_LIMIT))
    scenes = [to_imagery_scene(zone_id, candidate) for candidate in select_scenes(candidates)[:limit]]
    for scene in scenes:
        await try_save_scene(scene)
    return ImagerySceneCollection(zone_id=zone_id, scenes=scenes)


async def get_latest_zone_imagery_for_api(zone_id: str, polygon: list[list[float]]) -> ImageryScene:
    scene = await get_latest_zone_imagery(zone_id, polygon)
    return to_preview_scene(scene)


async def get_zone_imagery_history_for_api(
    zone_id: str,
    polygon: list[list[float]],
    limit: int = HISTORY_LIMIT,
) -> ImagerySceneCollection:
    history = await get_zone_imagery_history(zone_id, polygon, limit=limit)
    return ImagerySceneCollection(zone_id=history.zone_id, scenes=[to_preview_scene(scene) for scene in history.scenes])


async def get_scene_for_preview(scene_id: str) -> ImageryScene | None:
    try:
        return await load_scene(scene_id)
    except Exception:
        return None


async def try_load_latest_scene(zone_id: str) -> ImageryScene | None:
    try:
        return await load_latest_scene(zone_id)
    except Exception:
        return None


async def try_load_latest_scene_row(zone_id: str) -> dict[str, Any] | None:
    try:
        return await load_latest_scene_row(zone_id)
    except Exception:
        return None


async def try_load_scene_history(zone_id: str, limit: int) -> ImagerySceneCollection:
    try:
        return await load_scene_history(zone_id, limit)
    except Exception:
        return ImagerySceneCollection(zone_id=zone_id, scenes=[])


async def try_load_scene_history_rows(zone_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        return await load_scene_history_rows(zone_id, limit)
    except Exception:
        return []


async def try_save_scene(scene: ImageryScene) -> None:
    try:
        await save_scene(scene)
    except Exception:
        return


async def search_sentinel_scenes(polygon: list[list[float]], limit: int = HISTORY_LIMIT) -> list[SceneCandidate]:
    payload = build_stac_search_payload(polygon, limit=limit)
    timeout = httpx.Timeout(get_settings().IMAGERY_TIMEOUT_MS / 1000)
    try:
        async with httpx.AsyncClient(base_url=EARTH_SEARCH_BASE_URL, timeout=timeout) as client:
            response = await client.post("/search", json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Imagery service unavailable",
            status_code=502,
            details={"service": "earth-search"},
        ) from exc

    return [candidate for item in body.get("features", []) if (candidate := parse_stac_item(item)) is not None]


async def try_load_latest_scene(zone_id: str) -> ImageryScene | None:
    try:
        return await load_latest_scene(zone_id)
    except Exception:
        return None


async def try_load_latest_scene_row(zone_id: str) -> dict[str, Any] | None:
    try:
        return await load_latest_scene_row(zone_id)
    except Exception:
        return None


async def try_load_scene_history(zone_id: str, limit: int) -> ImagerySceneCollection:
    try:
        return await load_scene_history(zone_id, limit)
    except Exception:
        return ImagerySceneCollection(zone_id=zone_id, scenes=[])


async def try_load_scene_history_rows(zone_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        return await load_scene_history_rows(zone_id, limit)
    except Exception:
        return []


async def try_save_scene(scene: ImageryScene) -> None:
    try:
        await save_scene(scene)
    except Exception:
        return


async def search_sentinel_scenes(polygon: list[list[float]], limit: int = HISTORY_LIMIT) -> list[SceneCandidate]:
    payload = build_stac_search_payload(polygon, limit=limit)
    timeout = httpx.Timeout(get_settings().IMAGERY_TIMEOUT_MS / 1000)
    try:
        async with httpx.AsyncClient(base_url=EARTH_SEARCH_BASE_URL, timeout=timeout) as client:
            response = await client.post("/search", json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Imagery service unavailable",
            status_code=502,
            details={"service": "earth-search"},
        ) from exc

    return [candidate for item in body.get("features", []) if (candidate := parse_stac_item(item)) is not None]


def build_stac_search_payload(polygon: list[list[float]], limit: int = HISTORY_LIMIT) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=45)
    return {
        "collections": [SENTINEL_COLLECTION],
        "intersects": {"type": "Polygon", "coordinates": [polygon]},
        "datetime": f"{start.isoformat()}/{now.isoformat()}",
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }


def parse_stac_item(item: dict[str, Any]) -> SceneCandidate | None:
    properties = item.get("properties", {})
    acquisition_raw = properties.get("datetime")
    if not isinstance(acquisition_raw, str):
        return None

    cloud_cover = properties.get("eo:cloud_cover", properties.get("cloud_cover", 100.0))
    if not isinstance(cloud_cover, int | float) or cloud_cover >= MAX_CLOUD_COVER:
        return None

    scene_id = item.get("id")
    if not isinstance(scene_id, str) or not scene_id:
        return None

    assets = item.get("assets", {})
    rgb_url = get_asset_href(assets, ("visual", "thumbnail"))
    ndvi_url = get_asset_href(assets, ("nir", "nir08", "B08"))
    try:
        acquisition_time = parse_datetime(acquisition_raw)
    except ValueError:
        return None

    return SceneCandidate(
        scene_id=scene_id,
        acquisition_time=acquisition_time,
        cloud_cover=float(cloud_cover),
        coverage=float(properties.get("s2:valid_pixel_percentage", 80.0)) / 100,
        rgb_url=rgb_url,
        ndvi_url=ndvi_url,
        source=SENTINEL_COLLECTION,
    )


def get_asset_href(assets: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        asset = assets.get(name)
        if isinstance(asset, dict) and isinstance(asset.get("href"), str):
            return asset["href"]
    return None


def select_scenes(candidates: list[SceneCandidate]) -> list[SceneCandidate]:
    now = datetime.now(timezone.utc)
    return sorted(candidates, key=lambda scene: score_scene(scene, now), reverse=True)


def score_scene(scene: SceneCandidate, now: datetime) -> float:
    age_days = max((now - scene.acquisition_time).total_seconds() / 86400, 0.0)
    recency = max(0.0, 1.0 - age_days / 45)
    cloud = max(0.0, 1.0 - scene.cloud_cover / MAX_CLOUD_COVER)
    coverage = min(max(scene.coverage, 0.0), 1.0)
    return recency * 0.4 + cloud * 0.4 + coverage * 0.2


def to_imagery_scene(zone_id: str, scene: SceneCandidate) -> ImageryScene:
    return ImageryScene(
        zone_id=zone_id,
        scene_id=scene.scene_id,
        acquisition_time=scene.acquisition_time,
        cloud_cover=scene.cloud_cover,
        rgb_url=scene.rgb_url,
        ndvi_url=scene.ndvi_url,
        source=scene.source,
        stale=is_scene_old(scene.acquisition_time),
    )


def to_preview_scene(scene: ImageryScene) -> ImageryScene:
    if not scene.scene_id:
        return scene
    return scene.model_copy(
        update={
            "rgb_url": build_preview_url(scene.scene_id, "rgb"),
            "ndvi_url": build_preview_url(scene.scene_id, "ndvi"),
        }
    )


def build_preview_url(scene_id: str, mode: str) -> str:
    return f"{PREVIEW_BASE_PATH}/{scene_id}?mode={mode}"


def build_stale_scene(zone_id: str) -> ImageryScene:
    return ImageryScene(
        zone_id=zone_id,
        scene_id=None,
        acquisition_time=None,
        cloud_cover=None,
        rgb_url=None,
        ndvi_url=None,
        source="earth-search",
        stale=True,
    )


def is_scene_old(acquisition_time: datetime | None) -> bool:
    if acquisition_time is None:
        return True
    return (datetime.now(timezone.utc) - acquisition_time) > timedelta(days=STALE_SCENE_AGE_DAYS)


def is_metadata_row_fresh(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    fetched_at = fetched_at_from_row(row)
    if fetched_at is None:
        return False
    return fetched_at >= metadata_fresh_after()


def are_history_rows_fresh(rows: list[dict[str, Any]], limit: int) -> bool:
    if len(rows) < limit:
        return False
    return all(is_metadata_row_fresh(row) for row in rows[:limit])


def metadata_fresh_after() -> datetime:
    ttl = timedelta(seconds=get_settings().IMAGERY_METADATA_CACHE_TTL_SECONDS)
    return datetime.now(timezone.utc) - ttl


def parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
