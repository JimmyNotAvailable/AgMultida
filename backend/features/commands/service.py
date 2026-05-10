from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.config import Settings
from core.errors import AgTechError
from core.schemas import IrrigationCommandRequest
from features.commands.policy import evaluate_command_safety
from features.prediction.cache import PredictionCacheService

logger = logging.getLogger("agmultida.commands")


class CommandSafetyService:
    def __init__(self, prediction_cache: PredictionCacheService, settings: Settings) -> None:
        self._prediction_cache = prediction_cache
        self._settings = settings

    async def ensure_allowed(self, req: IrrigationCommandRequest, *, ack_override: bool) -> None:
        entry = await self._prediction_cache.get_latest(req.zone_id)
        allowed, error_code, message = evaluate_command_safety(
            entry,
            zone_id=req.zone_id,
            app_env=self._settings.ENV,
            ack_override=ack_override,
            has_operator_note=bool(req.operator_note and req.operator_note.strip()),
        )
        if allowed:
            return

        prediction = entry.response if entry is not None else None
        details = {
            "zone_id": req.zone_id,
            "trace_id": str(prediction.trace_id) if prediction is not None else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uncertainty": prediction.uncertainty if prediction is not None else None,
            "degraded_mode": prediction.degraded_mode if prediction is not None else None,
            "ack_override": ack_override,
        }
        self._log_rejection(req.zone_id, str(error_code.value), details)
        raise AgTechError(
            error_code=error_code,
            message=message or "Command blocked by safety gate",
            details=details,
            status_code=409,
        )

    def _log_rejection(self, zone_id: str, reason: str, details: dict) -> None:
        logger.info(
            "command_rejected",
            extra={
                "event": "command_rejected",
                "zone_id": zone_id,
                "reason": reason,
                "uncertainty": details["uncertainty"],
                "degraded_mode": details["degraded_mode"],
                "trace_id": details["trace_id"],
                "timestamp": details["timestamp"],
                "ack_override": details["ack_override"],
            },
        )
