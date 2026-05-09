from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from core.schemas import AlertRecord


class AlertEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    timestamp: datetime
    stress_prob: float = Field(ge=0.0, le=1.0)
    soil_moisture: float = Field(ge=0.0, le=100.0)
    rain_forecast_3h: float = Field(ge=0.0, le=1.0)
    imagery_acquisition_time: datetime | None = None
    sensor_last_seen: datetime | None = None


@dataclass
class AlertRepository:
    dedupe_window: timedelta = timedelta(hours=1)
    _last_seen: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def should_emit(self, zone_id: str, rule_id: str, timestamp: datetime) -> bool:
        key = (zone_id, rule_id)
        previous = self._last_seen.get(key)
        if previous is not None and timestamp - previous <= self.dedupe_window:
            return False
        self._last_seen = {
            **self._last_seen,
            key: timestamp,
        }
        return True


def evaluate_alerts(payload: AlertEvaluationInput, repository: AlertRepository | None = None) -> list[AlertRecord]:
    active_repository = repository or AlertRepository()
    alerts: list[AlertRecord] = []

    if payload.stress_prob > 0.6 and payload.soil_moisture < 25 and payload.rain_forecast_3h < 0.2:
        alerts.append(_make_alert(payload, "critical_stress_low_moisture", "critical", "High stress with low moisture and weak rain forecast"))
    elif payload.stress_prob > 0.4 and payload.soil_moisture < 30:
        alerts.append(_make_alert(payload, "warning_stress_low_moisture", "warning", "Rising stress with low moisture"))

    if payload.imagery_acquisition_time is not None and payload.timestamp - payload.imagery_acquisition_time > timedelta(days=7):
        alerts.append(_make_alert(payload, "imagery_stale", "info", "Latest imagery is older than 7 days"))

    if payload.sensor_last_seen is not None and payload.timestamp - payload.sensor_last_seen > timedelta(hours=2):
        alerts.append(_make_alert(payload, "sensor_missing", "degraded", "Sensor telemetry missing for more than 2 hours"))

    return [
        alert
        for alert in alerts
        if active_repository.should_emit(alert.zone_id, alert.rule_id, alert.timestamp)
    ]


def _make_alert(payload: AlertEvaluationInput, rule_id: str, severity: str, message: str) -> AlertRecord:
    return AlertRecord(
        alert_id=f"{payload.zone_id.lower()}-{rule_id}-{int(payload.timestamp.timestamp())}",
        zone_id=payload.zone_id,
        rule_id=rule_id,
        severity=severity,
        source="alert_engine",
        message=message,
        acknowledged=False,
        timestamp=payload.timestamp,
    )
