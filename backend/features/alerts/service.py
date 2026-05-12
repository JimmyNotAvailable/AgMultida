from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from backend.core.errors import AgTechError, ErrorCode
from backend.core.schemas import AlertRecord, IrrigationDecision, PredictResponse, RecAction
from backend.features.alerts.lifecycle import ALERT_STATUS_ACKNOWLEDGED, ALERT_STATUS_OPEN
from backend.features.alerts.stream import AlertStream

logger = logging.getLogger("agmultida.alerts")


@dataclass(frozen=True)
class LifecycleAlert:
    alert_id: str
    zone_id: str
    rule_id: str
    severity: str
    source: str
    message: str
    status: str
    created_at: datetime
    acknowledged: bool = False
    telegram_sent: bool = False
    require_review: bool = False

    def to_record(self) -> AlertRecord:
        return AlertRecord(
            alert_id=self.alert_id,
            zone_id=self.zone_id,
            rule_id=self.rule_id,
            severity=self.severity,
            source=self.source,
            message=f"{self.message} [status={self.status}; telegram_sent={str(self.telegram_sent).lower()}]",
            acknowledged=self.acknowledged,
            timestamp=self.created_at,
        )

    def to_payload(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "zone_id": self.zone_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "source": self.source,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "telegram_sent": self.telegram_sent,
            "require_review": self.require_review,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "LifecycleAlert":
        return cls(
            alert_id=payload["alert_id"],
            zone_id=payload["zone_id"],
            rule_id=payload["rule_id"],
            severity=payload["severity"],
            source=payload["source"],
            message=payload["message"],
            status=payload["status"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            acknowledged=payload.get("acknowledged", False),
            telegram_sent=payload.get("telegram_sent", False),
            require_review=payload.get("require_review", False),
        )


class AlertService:
    def __init__(self, redis_client: object | None = None, stream: AlertStream | None = None, open_ttl_seconds: int = 86_400) -> None:
        self._redis_client = redis_client
        self._stream = stream or AlertStream(redis_client)
        self._open_ttl_seconds = open_ttl_seconds
        self._alerts: dict[str, LifecycleAlert] = {}
        self._open_by_zone: dict[str, list[str]] = {}
        self._dedupe: dict[str, str] = {}

    async def create_for_recommendation(
        self,
        zone_id: str,
        decision: IrrigationDecision,
        prediction: PredictResponse | None,
        *,
        imagery_stale: bool = False,
    ) -> LifecycleAlert | None:
        trigger = _recommendation_trigger(decision, prediction, imagery_stale)
        if trigger is None:
            return None
        started = time.perf_counter()
        dedupe_key = _dedupe_key(zone_id, trigger["type"])
        existing_id = self._dedupe.get(dedupe_key)
        if existing_id is not None:
            return self._alerts.get(existing_id)
        alert = LifecycleAlert(
            alert_id=f"alert_{uuid4().hex[:12]}",
            zone_id=zone_id,
            rule_id=trigger["type"],
            severity=trigger["severity"],
            source="alert_lifecycle",
            message=trigger["reason"],
            status=ALERT_STATUS_OPEN,
            created_at=datetime.now(timezone.utc),
            require_review=trigger.get("require_review", False),
        )
        self._dedupe[dedupe_key] = alert.alert_id
        await self._store(alert)
        await self._stream.append({"event": "alert_created", **alert.to_payload()})
        self._log_created(alert, round((time.perf_counter() - started) * 1000, 2))
        return alert

    async def list_zone_alerts(self, zone_id: str, *, limit: int) -> list[AlertRecord]:
        await self._load_zone(zone_id)
        ids = self._open_by_zone.get(zone_id, [])
        alerts = [self._alerts[alert_id].to_record() for alert_id in ids if alert_id in self._alerts]
        return alerts[:limit]

    async def acknowledge(self, alert_id: str) -> AlertRecord:
        alert = await self._get(alert_id)
        if alert is None:
            raise AgTechError(
                error_code=ErrorCode.ZONE_NOT_FOUND,
                message="Alert not found",
                details={"alert_id": alert_id},
                status_code=404,
            )
        if alert.status in {ALERT_STATUS_ACKNOWLEDGED, "resolved"}:
            raise AgTechError(
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Alert already acknowledged or resolved",
                details={"alert_id": alert_id, "status": alert.status},
                status_code=409,
            )
        updated = LifecycleAlert(
            alert_id=alert.alert_id,
            zone_id=alert.zone_id,
            rule_id=alert.rule_id,
            severity=alert.severity,
            source=alert.source,
            message=alert.message,
            status=ALERT_STATUS_ACKNOWLEDGED,
            created_at=alert.created_at,
            acknowledged=True,
            telegram_sent=alert.telegram_sent,
            require_review=alert.require_review,
        )
        logger.info(
            "alert_acknowledged",
            extra={
                "event": "alert_acknowledged",
                "alert_id": updated.alert_id,
                "zone_id": updated.zone_id,
                "type": updated.rule_id,
                "severity": updated.severity,
            },
        )
        await self._store(updated)
        await self._stream.append({"event": "alert_acknowledged", **updated.to_payload()})
        return updated.to_record()

    async def _store(self, alert: LifecycleAlert) -> None:
        self._alerts[alert.alert_id] = alert
        zone_ids = [item for item in self._open_by_zone.get(alert.zone_id, []) if item != alert.alert_id]
        if not alert.acknowledged:
            zone_ids.insert(0, alert.alert_id)
        self._open_by_zone[alert.zone_id] = zone_ids
        if self._redis_client is None:
            return
        try:
            alert_key = f"alert:{alert.alert_id}"
            await self._redis_client.hset(alert_key, mapping={"payload": json.dumps(alert.to_payload(), separators=(",", ":"))})
            await self._redis_client.expire(alert_key, 604_800)
            if not alert.acknowledged:
                zone_open_key = f"alerts:zone:{alert.zone_id}:open"
                await self._redis_client.lpush(zone_open_key, alert.alert_id)
                await self._redis_client.expire(zone_open_key, self._open_ttl_seconds)
        except Exception:
            return

    async def _get(self, alert_id: str) -> LifecycleAlert | None:
        alert = self._alerts.get(alert_id)
        if alert is not None:
            return alert
        if self._redis_client is None:
            return None
        try:
            payload = await self._redis_client.hget(f"alert:{alert_id}", "payload")
        except Exception:
            return None
        if payload is None:
            return None
        try:
            raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            alert = LifecycleAlert.from_payload(json.loads(raw))
        except Exception:
            return None
        self._alerts[alert.alert_id] = alert
        return alert

    async def _load_zone(self, zone_id: str) -> None:
        if self._redis_client is None or self._open_by_zone.get(zone_id):
            return
        try:
            ids = await self._redis_client.lrange(f"alerts:zone:{zone_id}:open", 0, -1)
        except Exception:
            return
        self._open_by_zone[zone_id] = [item.decode("utf-8") if isinstance(item, bytes) else item for item in ids]
        for alert_id in self._open_by_zone[zone_id]:
            await self._get(alert_id)

    def _log_created(self, alert: LifecycleAlert, latency_ms: float) -> None:
        logger.info(
            "alert_created",
            extra={
                "event": "alert_created",
                "alert_id": alert.alert_id,
                "zone_id": alert.zone_id,
                "type": alert.rule_id,
                "severity": alert.severity,
                "trigger_reason": alert.message,
                "trace_id": str(uuid4()),
                "latency_ms": latency_ms,
            },
        )


def _recommendation_trigger(decision: IrrigationDecision, prediction: PredictResponse | None, imagery_stale: bool) -> dict | None:
    stress_prob = prediction.stress_prob if prediction is not None else 0.0
    uncertainty = prediction.uncertainty if prediction is not None else 0.0
    degraded = decision.degraded_mode or (prediction.degraded_mode if prediction is not None else False)
    if decision.action != RecAction.NO_IRRIGATION:
        return {"type": "irrigation_action", "severity": "moderate", "reason": f"Recommended action: {decision.action.value}"}
    if uncertainty > 0.15:
        return {
            "type": "uncertainty_watch",
            "severity": "watch",
            "reason": "Prediction uncertainty above alert threshold",
            "require_review": uncertainty > 0.30,
        }
    if degraded:
        return {"type": "degraded_prediction", "severity": "moderate", "reason": "Recommendation uses degraded prediction"}
    if stress_prob >= 0.60:
        return {"type": "critical_stress", "severity": "critical", "reason": "Critical stress probability"}
    if imagery_stale:
        return {"type": "imagery_stale", "severity": "watch", "reason": "Imagery metadata is stale"}
    return None


def _dedupe_key(zone_id: str, alert_type: str) -> str:
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    return hashlib.sha256(f"{zone_id}:{alert_type}:{bucket}".encode()).hexdigest()
