from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.api_gateway.clients.decision_client import LiveDecisionClient
from backend.core.schemas import (
    AlertRecord,
    AlertSummary,
    CommandStatus,
    ConfidenceFlag,
    ImagerySummary,
    PredictResponse,
    RecommendRequest,
    ZoneStatusResponse,
)
from backend.core.weather import ZoneWeatherResponse
from backend.decision_engine.alert_engine import AlertEvaluationInput, AlertRepository, evaluate_alerts


def build_zone_status(zone_id: str, weather: ZoneWeatherResponse) -> ZoneStatusResponse:
    now = datetime.now(timezone.utc)
    latest_prediction = PredictResponse(
        zone_id=zone_id,
        timestamp=now,
        stress_prob=0.62 if zone_id in {"A03", "F01"} else 0.38,
        uncertainty=0.16 if zone_id in {"A01", "E01"} else 0.29,
        confidence_flag=ConfidenceFlag.MEDIUM,
        degraded_mode=False,
        attention_weights=[0.4, 0.35, 0.25],
        model_version="status-aggregate-demo",
        explanation=[],
        latency_ms=42.0,
    )
    rain_3h = extract_rain_3h(weather)
    moisture = 21.0 if zone_id in {"A03", "F01"} else 34.0
    latest_decision = LiveDecisionClient().recommend(
        RecommendRequest(
            zone_id=zone_id,
            stress_prob=latest_prediction.stress_prob,
            uncertainty=latest_prediction.uncertainty,
            degraded_mode=latest_prediction.degraded_mode,
            soil_moisture=moisture,
            rain_forecast_3h=rain_3h,
            attention_weights=latest_prediction.attention_weights,
        )
    )
    latest_telemetry = {
        "soil_moisture": moisture,
        "air_temp": weather.current.temperature_2m if weather.current else None,
        "humidity": weather.current.relative_humidity_2m if weather.current else None,
        "rain_3h": rain_3h,
        "source": "zone_status_aggregate",
        "timestamp": now.isoformat(),
    }
    alerts = build_alerts(zone_id, latest_prediction.stress_prob, moisture, rain_3h, now)
    imagery = ImagerySummary(
        scene_id=f"stub-scene-{zone_id.lower()}",
        acquisition_time=now - timedelta(days=5),
        cloud_cover=12.5,
        rgb_url=None,
        ndvi_url=None,
        stale=False,
    )
    return ZoneStatusResponse(
        zone_id=zone_id,
        latest_prediction=latest_prediction,
        latest_decision=latest_decision,
        latest_telemetry=latest_telemetry,
        weather=weather.model_dump(mode="json"),
        imagery=imagery,
        alerts=alerts,
        command_state=CommandStatus.PENDING,
        updated_at=now,
    )


def build_alerts(zone_id: str, stress_prob: float, moisture: float, rain_3h: float, now: datetime) -> list[AlertSummary]:
    return [
        AlertSummary(
            alert_id=alert.alert_id,
            severity=alert.severity,
            source=alert.source,
            message=alert.message,
            acknowledged=alert.acknowledged,
            timestamp=alert.timestamp,
        )
        for alert in build_zone_alert_records(
            zone_id,
            now,
            stress_prob=stress_prob,
            moisture=moisture,
            rain_3h=rain_3h,
        )
    ]


def build_zone_alert_records(
    zone_id: str,
    now: datetime,
    *,
    stress_prob: float | None = None,
    moisture: float | None = None,
    rain_3h: float | None = None,
    repository: AlertRepository | None = None,
) -> list[AlertRecord]:
    derived_stress = stress_prob if stress_prob is not None else (0.62 if zone_id in {"A03", "F01"} else 0.38)
    derived_moisture = moisture if moisture is not None else (21.0 if zone_id in {"A03", "F01"} else 34.0)
    derived_rain = rain_3h if rain_3h is not None else 0.12
    return evaluate_alerts(
        AlertEvaluationInput(
            zone_id=zone_id,
            timestamp=now,
            stress_prob=derived_stress,
            soil_moisture=derived_moisture,
            rain_forecast_3h=derived_rain,
            imagery_acquisition_time=now - timedelta(days=5),
            sensor_last_seen=now - timedelta(minutes=30),
        ),
        repository or AlertRepository(),
    )


def extract_rain_3h(weather: ZoneWeatherResponse) -> float:
    if weather.hourly is None or not weather.hourly.precipitation_probability:
        return 0.0
    next_values = weather.hourly.precipitation_probability[:3]
    filtered = [value for value in next_values if value is not None]
    if not filtered:
        return 0.0
    return max(filtered) / 100
