from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode
from backend.core.geospatial import calculate_centroid
from backend.core.http_client import fetch_with_retry
from backend.core.weather import ZoneWeatherResponse
from backend.infra.cache import TieredCache, json_decoder, json_encoder

_weather_cache: TieredCache[dict] | None = None


def get_weather_cache() -> TieredCache[dict]:
    global _weather_cache
    if _weather_cache is None:
        settings = get_settings()
        _weather_cache = TieredCache(
            namespace="weather",
            ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
            redis_ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
        )
    return _weather_cache


async def fetch_weather_for_zone(zone_id: str, polygon: list[list[float]]) -> ZoneWeatherResponse:
    latitude, longitude = calculate_centroid(polygon)
    settings = get_settings()
    cache_key = f"{zone_id}:latest"
    cached = await get_weather_cache().get(cache_key, json_decoder)
    if cached is not None:
        return ZoneWeatherResponse.model_validate(cached)
    timeout = httpx.Timeout(settings.WEATHER_TIMEOUT_MS / 1000)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation",
        "forecast_days": 3,
        "timezone": "UTC",
    }

    try:
        async with httpx.AsyncClient(base_url=settings.WEATHER_API_BASE_URL, timeout=timeout) as client:
            response = await fetch_with_retry(client, "GET", "/forecast", params=params)
            body = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Weather service unavailable",
            status_code=502,
            details={"service": "open-meteo", "zone_id": zone_id},
        ) from exc

    current_raw = body.get("current", {})
    current = {
        "time": current_raw.get("time"),
        "temperature_2m": current_raw.get("temperature_2m"),
        "relative_humidity_2m": current_raw.get("relative_humidity_2m"),
        "precipitation": current_raw.get("precipitation"),
        "wind_speed_10m": current_raw.get("wind_speed_10m"),
    }
    hourly = body.get("hourly", {})
    weather = ZoneWeatherResponse.model_validate(
        {
            "zone_id": zone_id,
            "latitude": latitude,
            "longitude": longitude,
            "current": current if current.get("time") else None,
            "hourly": {
                "time": hourly.get("time", []),
                "temperature_2m": hourly.get("temperature_2m", []),
                "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
                "precipitation_probability": hourly.get("precipitation_probability", []),
                "precipitation": hourly.get("precipitation", []),
            },
            "updated_at": datetime.now(timezone.utc),
        }
    )
    await get_weather_cache().set(cache_key, weather.model_dump(mode="json"), json_encoder)
    return weather
