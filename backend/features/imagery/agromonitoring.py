from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode
from backend.core.http_client import fetch_with_retry

AGRO_BASE_URL = "http://api.agromonitoring.com/agro/1.0"
IMAGERY_SEARCH_LOOKBACK_DAYS = 30
MAX_CLOUD_PERCENT = 25.0

ZONE_POLYGONS: dict[str, list[list[float]]] = {
    "DT01": [
        [105.921894, 10.454166],
        [105.929597, 10.453069],
        [105.928803, 10.438994],
        [105.921679, 10.444522],
        [105.921894, 10.454166],
    ],
    "TN01": [
        [106.012877, 10.721116],
        [106.019098, 10.725379],
        [106.029082, 10.714467],
        [106.019159, 10.710084],
        [106.012877, 10.721116],
    ],
}

_polygon_id_cache: dict[str, str] = {}


@dataclass(frozen=True)
class SpectralScene:
    zone_id: str
    dt: int
    satellite: str
    cloud_cover: float
    data_coverage: float
    ndvi_image_url: str | None
    evi_image_url: str | None
    truecolor_image_url: str | None
    falsecolor_image_url: str | None
    ndvi_tile_url: str | None
    ndvi_stats_url: str | None


@dataclass(frozen=True)
class NdviHistoryPoint:
    dt: int
    source: str
    cloud_cover: float
    mean: float
    median: float
    min: float
    max: float
    std: float
    p25: float
    p75: float


@dataclass(frozen=True)
class SpectralResponse:
    zone_id: str
    polygon_id: str
    scenes: list[SpectralScene]
    ndvi_history: list[NdviHistoryPoint]


def _get_api_key() -> str:
    key = get_settings().AGROMONITORING_API_KEY
    if not key:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Agromonitoring API key not configured",
            status_code=503,
            details={"service": "agromonitoring"},
        )
    return key


async def _ensure_polygon_registered(zone_id: str) -> str:
    if zone_id in _polygon_id_cache:
        return _polygon_id_cache[zone_id]

    coordinates = ZONE_POLYGONS.get(zone_id)
    if coordinates is None:
        raise AgTechError(
            error_code=ErrorCode.ZONE_NOT_FOUND,
            message=f"No polygon defined for zone {zone_id}",
            status_code=404,
            details={"zone_id": zone_id},
        )

    api_key = _get_api_key()
    payload = {
        "name": f"AgMultida-{zone_id}",
        "geo_json": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
        },
    }

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await fetch_with_retry(
                client,
                "POST",
                f"{AGRO_BASE_URL}/polygons?appid={api_key}&duplicated=true",
                json=payload,
            )
            body = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Agromonitoring polygon registration failed",
            status_code=502,
            details={"service": "agromonitoring"},
        ) from exc

    polygon_id = body.get("id")
    if not isinstance(polygon_id, str):
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Agromonitoring returned invalid polygon response",
            status_code=502,
            details={"response": body},
        )

    _polygon_id_cache[zone_id] = polygon_id
    return polygon_id


async def search_spectral_imagery(zone_id: str, lookback_days: int = IMAGERY_SEARCH_LOOKBACK_DAYS) -> list[SpectralScene]:
    polygon_id = await _ensure_polygon_registered(zone_id)
    api_key = _get_api_key()

    end_ts = int(time.time())
    start_ts = end_ts - lookback_days * 86400

    url = (
        f"{AGRO_BASE_URL}/image/search"
        f"?start={start_ts}&end={end_ts}"
        f"&polyid={polygon_id}"
        f"&appid={api_key}"
    )

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await fetch_with_retry(client, "GET", url)
            items: list[dict[str, Any]] = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Agromonitoring imagery search failed",
            status_code=502,
            details={"service": "agromonitoring"},
        ) from exc

    if not isinstance(items, list):
        return []

    scenes: list[SpectralScene] = []
    for item in items:
        cloud = item.get("cl", 100.0)
        if not isinstance(cloud, int | float) or cloud > MAX_CLOUD_PERCENT:
            continue
        image = item.get("image", {})
        tile = item.get("tile", {})
        stats = item.get("stats", {})
        scenes.append(
            SpectralScene(
                zone_id=zone_id,
                dt=item.get("dt", 0),
                satellite=item.get("type", "unknown"),
                cloud_cover=float(cloud),
                data_coverage=float(item.get("dc", 0)),
                ndvi_image_url=image.get("ndvi"),
                evi_image_url=image.get("evi"),
                truecolor_image_url=image.get("truecolor"),
                falsecolor_image_url=image.get("falsecolor"),
                ndvi_tile_url=tile.get("ndvi"),
                ndvi_stats_url=stats.get("ndvi"),
            )
        )

    scenes.sort(key=lambda s: s.dt, reverse=True)
    return scenes


async def fetch_ndvi_history(zone_id: str, lookback_days: int = 90) -> list[NdviHistoryPoint]:
    polygon_id = await _ensure_polygon_registered(zone_id)
    api_key = _get_api_key()

    end_ts = int(time.time())
    start_ts = end_ts - lookback_days * 86400

    url = (
        f"{AGRO_BASE_URL}/ndvi/history"
        f"?start={start_ts}&end={end_ts}"
        f"&polyid={polygon_id}"
        f"&appid={api_key}"
    )

    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await fetch_with_retry(client, "GET", url)
            items: list[dict[str, Any]] = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Agromonitoring NDVI history fetch failed",
            status_code=502,
            details={"service": "agromonitoring"},
        ) from exc

    if not isinstance(items, list):
        return []

    history: list[NdviHistoryPoint] = []
    for item in items:
        data = item.get("data", {})
        if not isinstance(data, dict) or "mean" not in data:
            continue
        history.append(
            NdviHistoryPoint(
                dt=item.get("dt", 0),
                source=item.get("source", "unknown"),
                cloud_cover=float(item.get("cl", 0)),
                mean=float(data.get("mean", 0)),
                median=float(data.get("median", 0)),
                min=float(data.get("min", 0)),
                max=float(data.get("max", 0)),
                std=float(data.get("std", 0)),
                p25=float(data.get("p25", 0)),
                p75=float(data.get("p75", 0)),
            )
        )

    history.sort(key=lambda h: h.dt)
    return history


async def get_zone_spectral(zone_id: str) -> SpectralResponse:
    polygon_id = await _ensure_polygon_registered(zone_id)
    scenes = await search_spectral_imagery(zone_id)
    ndvi_history = await fetch_ndvi_history(zone_id)
    return SpectralResponse(
        zone_id=zone_id,
        polygon_id=polygon_id,
        scenes=scenes,
        ndvi_history=ndvi_history,
    )
