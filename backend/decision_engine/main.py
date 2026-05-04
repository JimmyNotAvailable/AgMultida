"""Decision Engine: hybrid rule engine for irrigation recommendations.

Architecture ref: backend/decision-engine -> backend/decision_engine.
Consumes prediction output, applies rule chain from decision_contract.yaml.
STUB: logic implemented per contract, Redis Stream + MQTT deferred to Batch 3+.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.schemas import (
    ConfidenceFlag,
    IrrigationDecision,
    RecAction,
    RecommendRequest,
)
from core.errors import AgTechError, mask_internal_exception

app = FastAPI(title="AgMultida Decision Engine", version="1.0.0")

# Thresholds synced with contracts/decision_contract.yaml
UNCERTAINTY_GATE = 0.30
RAIN_OVERRIDE = 0.40
CRITICAL_STRESS = 0.60
CRITICAL_MOISTURE = 25.0
MODERATE_STRESS = 0.40
MODERATE_MOISTURE = 30.0
EARLY_WATCH = 0.25
DEGRADED_UNCERTAINTY_MULT = 1.3

VOLUME_MAP = {
    RecAction.NO_IRRIGATION: 0.0,
    RecAction.LIGHT: 5.0,
    RecAction.MODERATE: 12.0,
    RecAction.HEAVY: 20.0,
    RecAction.HOLD: 0.0,
}


@app.exception_handler(AgTechError)
async def agtech_error_handler(request: Request, exc: AgTechError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response().model_dump(mode="json"),
    )


def evaluate_decision(req: RecommendRequest) -> IrrigationDecision:
    """Apply hybrid rule chain per decision_contract.yaml.

    Step order is critical: rain override -> uncertainty gate -> stress mapping.
    """
    uncertainty = req.uncertainty
    degraded = req.degraded_mode

    if degraded:
        uncertainty = uncertainty * DEGRADED_UNCERTAINTY_MULT

    # Step 1: Rain override
    if req.rain_forecast_3h > RAIN_OVERRIDE:
        return _decision(RecAction.NO_IRRIGATION, "rain_override", False, degraded)

    # Step 2: Uncertainty gate
    if uncertainty > UNCERTAINTY_GATE or degraded:
        return _decision(RecAction.HOLD, "high_uncertainty_or_degraded", True, degraded,
                         confidence=ConfidenceFlag.LOW)

    # Step 3: Critical stress
    if req.stress_prob > CRITICAL_STRESS and req.soil_moisture < CRITICAL_MOISTURE:
        return _decision(RecAction.HEAVY, "critical_stress_low_moisture", False, degraded)

    # Step 4: Moderate stress
    if req.stress_prob > MODERATE_STRESS and req.soil_moisture < MODERATE_MOISTURE:
        return _decision(RecAction.MODERATE, "moderate_stress", False, degraded)

    # Step 5: Early watch
    if req.stress_prob > EARLY_WATCH:
        return _decision(RecAction.LIGHT, "early_watch", False, degraded)

    # Step 6: Healthy
    return _decision(RecAction.NO_IRRIGATION, "healthy_range", False, degraded)


def _decision(
    action: RecAction,
    reason: str,
    require_ack: bool,
    degraded: bool,
    confidence: ConfidenceFlag = ConfidenceFlag.HIGH,
) -> IrrigationDecision:
    return IrrigationDecision(
        action=action,
        volume_mm=VOLUME_MAP[action],
        require_ack=require_ack,
        reason=reason,
        degraded_mode=degraded,
        confidence_flag=confidence,
    )


@app.post("/internal/recommend", response_model=IrrigationDecision)
async def internal_recommend(req: RecommendRequest):
    return evaluate_decision(req)
