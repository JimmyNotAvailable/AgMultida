from __future__ import annotations

from backend.core.schemas import IrrigationDecision, RecAction

RECOMMENDATION_LATEST_TTL_SECONDS = 600
RAIN_OVERRIDE_THRESHOLD_MM = 15.0
DEGRADED_VOLUME_REDUCTION_FACTOR = 0.5
UNCERTAINTY_HOLD_THRESHOLD = 0.30


def apply_recommendation_policy(decision: IrrigationDecision, *, rain_forecast_3h_mm: float, uncertainty: float, degraded_mode: bool) -> IrrigationDecision:
    if rain_forecast_3h_mm > RAIN_OVERRIDE_THRESHOLD_MM:
        return decision.model_copy(update={"action": RecAction.NO_IRRIGATION, "volume_mm": 0.0, "reason": "rain_override", "require_ack": False})
    if uncertainty > UNCERTAINTY_HOLD_THRESHOLD:
        return decision.model_copy(update={"action": RecAction.HOLD, "volume_mm": 0.0, "reason": "high_uncertainty_or_degraded", "require_ack": True})
    if degraded_mode:
        return decision.model_copy(update={"volume_mm": round(decision.volume_mm * DEGRADED_VOLUME_REDUCTION_FACTOR, 2), "reason": f"{decision.reason}_degraded", "require_ack": True})
    return decision
