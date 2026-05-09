"""Decision Engine: hybrid rule engine for irrigation recommendations.

Architecture ref: backend/decision-engine -> backend/decision_engine.
Consumes prediction output, applies rule chain from decision_contract.yaml.
STUB: logic implemented per contract, Redis Stream + MQTT deferred to Batch 3+.
"""
from __future__ import annotations

import hmac
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.schemas import (
    ConfidenceFlag,
    HealthResponse,
    IrrigationDecision,
    RecAction,
    RecommendRequest,
)
from core.errors import AgTechError, ErrorCode, mask_internal_exception

app = FastAPI(title="AgMultida Decision Engine", version="1.0.0")


def require_internal_api_key(request: Request) -> None:
    settings = get_settings()
    expected_key = settings.INTERNAL_API_KEY
    header_name = settings.INTERNAL_API_KEY_HEADER
    provided_key = request.headers.get(header_name)
    if not provided_key or not expected_key or not hmac.compare_digest(provided_key, expected_key):
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_API_KEY,
            message='Invalid internal API key.',
            details={'source_service': 'api_gateway'},
            status_code=401,
            trace_id=uuid4(),
        )


@app.get('/healthz', response_model=HealthResponse)
async def healthz():
    return HealthResponse()


@app.get('/readyz')
async def readyz() -> dict[str, str]:
    return {'status': 'ok'}

# Thresholds synced with contracts/decision_contract.yaml
UNCERTAINTY_GATE = 0.30
RAIN_OVERRIDE = 0.40
CRITICAL_STRESS = 0.60
CRITICAL_MOISTURE = 25.0
DEGRADED_UNCERTAINTY_MULT = 1.3
MODERATE_STRESS = 0.40
MODERATE_MOISTURE = 30.0
EARLY_WATCH = 0.25
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
async def internal_recommend(req: RecommendRequest, request: Request):
    require_internal_api_key(request)
    return evaluate_decision(req)
