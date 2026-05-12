from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from backend.core.config import get_settings
from backend.core.imagery import fetch_and_persist_zone_imagery_history
from backend.core.schemas import PredictRequest, RecommendRequest
from backend.features.zones.loader import load_zone_feature
from backend.features.websocket.publish import publish_realtime_event

logger = logging.getLogger("agmultida.imagery.polling")


async def sentinel_polling_loop(application: FastAPI) -> None:
    """Poll Sentinel imagery by zone and trigger the prediction/recommendation loop."""
    settings = get_settings()
    await asyncio.sleep(settings.SENTINEL_POLL_ZONE_DELAY_SECONDS)
    while True:
        try:
            zones = await application.state.zone_registry_service.list_zones()
        except Exception as exc:
            logger.warning("sentinel_polling_registry_error", extra={"error": str(exc)})
            await asyncio.sleep(settings.IMAGERY_POLL_INTERVAL_SECONDS)
            continue

        for item in zones:
            zone_id = item.zone.zone_id
            try:
                await process_zone_imagery(application, zone_id)
            except Exception as exc:
                logger.warning("sentinel_polling_zone_error", extra={"zone_id": zone_id, "error": str(exc)})
            await asyncio.sleep(settings.SENTINEL_POLL_ZONE_DELAY_SECONDS)

        await asyncio.sleep(settings.IMAGERY_POLL_INTERVAL_SECONDS)


async def process_zone_imagery(application: FastAPI, zone_id: str) -> None:
    """Refresh imagery for one zone and produce derived ML state."""
    zone_feature = load_zone_feature(zone_id)
    polygon = zone_feature["geometry"]["coordinates"][0]
    imagery = await fetch_and_persist_zone_imagery_history(zone_id, polygon, limit=1)
    if not imagery.scenes:
        return

    scene = imagery.scenes[0]
    scene_key = scene.scene_id or (scene.acquisition_time.isoformat() if scene.acquisition_time else None)
    processed = getattr(application.state, "sentinel_processed_scenes", {})
    if scene_key is not None and processed.get(zone_id) == scene_key:
        return
    timestamp = scene.acquisition_time or datetime.now(timezone.utc)
    prediction_request = PredictRequest(zone_id=zone_id, timestamp=timestamp)
    prediction = await application.state.ai_client.predict(prediction_request)
    prediction = await application.state.prediction_service.complete_prediction(prediction_request, prediction)

    status = await _get_status_for_features(application, zone_id)
    telemetry = status.latest_telemetry or {}
    weather = status.weather or {}
    soil_moisture = _number(telemetry.get("soil_moisture"), default=35.0, minimum=0.0, maximum=100.0)
    rain_forecast_3h = _rain_probability(telemetry, weather)

    decision = await application.state.recommendation_service.recommend(
        RecommendRequest(
            zone_id=zone_id,
            stress_prob=prediction.stress_prob,
            uncertainty=prediction.uncertainty,
            degraded_mode=prediction.degraded_mode,
            soil_moisture=soil_moisture,
            rain_forecast_3h=rain_forecast_3h,
            attention_weights=prediction.attention_weights,
        ),
        trace_id=str(prediction.trace_id),
    )

    if scene_key is not None:
        application.state.sentinel_processed_scenes = {**processed, zone_id: scene_key}
    application.state.zone_status_cache.invalidate(zone_id)
    await application.state.zone_status_aggregate.invalidate(zone_id)
    await publish_realtime_event(application, "prediction_completed", zone_id, {"zone_id": zone_id, "prediction_id": prediction.prediction_id})
    await publish_realtime_event(application, "recommendation_created", zone_id, {"zone_id": zone_id, "action": decision.action.value})


async def _get_status_for_features(application: FastAPI, zone_id: str):
    async def build_base_status():
        from backend.core.weather import ZoneWeatherResponse
        from backend.features.zones.status_builder import build_zone_status
        from backend.features.zones.weather import fetch_weather_for_zone

        zone_feature = load_zone_feature(zone_id)
        weather: ZoneWeatherResponse = await fetch_weather_for_zone(zone_id, zone_feature["geometry"]["coordinates"][0])
        return build_zone_status(zone_id=zone_id, weather=weather)

    return await application.state.zone_status_aggregate.get_or_build(zone_id, build_base_status)


def _number(value: object, *, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, int | float):
        return min(max(float(value), minimum), maximum)
    return default


def _rain_probability(telemetry: dict, weather: dict) -> float:
    telemetry_rain = telemetry.get("rain_forecast_3h", telemetry.get("rain_3h"))
    if isinstance(telemetry_rain, int | float):
        return min(max(float(telemetry_rain) / 100.0, 0.0), 1.0)

    hourly = weather.get("hourly") if isinstance(weather, dict) else None
    if isinstance(hourly, dict):
        values = hourly.get("precipitation_probability")
        if isinstance(values, list) and values:
            numeric = [float(value) for value in values[:3] if isinstance(value, int | float)]
            if numeric:
                return min(max(max(numeric) / 100.0, 0.0), 1.0)
    return 0.0
