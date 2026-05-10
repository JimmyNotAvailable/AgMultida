from __future__ import annotations

from datetime import datetime, timezone

from core.errors import ErrorCode
from features.prediction.cache import PredictionCacheEntry
from features.prediction.policy import PREDICTION_LATEST_TTL_SECONDS

COMMAND_UNCERTAINTY_THRESHOLD = 0.30


def evaluate_command_safety(
    entry: PredictionCacheEntry | None,
    *,
    zone_id: str,
    app_env: str,
    ack_override: bool,
    has_operator_note: bool,
) -> tuple[bool, ErrorCode | None, str | None]:
    if entry is None:
        return False, ErrorCode.COMMAND_BLOCKED_NO_RECENT_PREDICTION, "No recent prediction available for command safety gate"

    prediction = entry.response
    if prediction.zone_id != zone_id or _is_expired(entry.created_at):
        return False, ErrorCode.COMMAND_BLOCKED_NO_RECENT_PREDICTION, "No recent prediction available for command safety gate"
    if app_env == 'production' and entry.source == 'demo':
        return False, ErrorCode.COMMAND_BLOCKED_DEGRADED_PREDICTION, "Command blocked: demo prediction is not allowed in production"
    # TODO PR-05: Enforce command action/volume consistency against decision:{zone_id}:latest when recommendation cache is stable.
    if prediction.uncertainty > COMMAND_UNCERTAINTY_THRESHOLD:
        return False, ErrorCode.COMMAND_BLOCKED_HIGH_UNCERTAINTY, "Command blocked: prediction uncertainty exceeds safety threshold"
    if prediction.degraded_mode and (not ack_override or not has_operator_note):
        return False, ErrorCode.COMMAND_BLOCKED_DEGRADED_PREDICTION, "Command blocked: degraded prediction requires acknowledgement and operator note"
    return True, None, None


def _is_expired(created_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    normalized = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
    return (now - normalized).total_seconds() > PREDICTION_LATEST_TTL_SECONDS
