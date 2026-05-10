from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.core.config import get_settings
from backend.core.errors import AgTechError, ErrorCode
from backend.core.geospatial import calculate_centroid
from backend.core.weather import ZoneWeatherResponse


async def fetch_weather_for_zone(zone_id: str, polygon: list[list[float]]) -> ZoneWeatherResponse:
    latitude, longitude = calculate_centroid(polygon)
    settings = get_settings()
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
            response = await client.get("/forecast", params=params)
            response.raise_for_status()
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
    return ZoneWeatherResponse.model_validate(
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
