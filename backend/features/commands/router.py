from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Query, Request

from backend.core.schemas import CommandStatus, IrrigationCommandRequest, IrrigationCommandResponse, PredictRequest

router = APIRouter(tags=["commands"])


@router.post("/v1/commands", response_model=IrrigationCommandResponse)
async def create_command(req: IrrigationCommandRequest, request: Request, ack: bool = Query(default=False)):
    await _seed_admin_stub_prediction(req, request)
    await request.app.state.command_safety_service.ensure_allowed(req, ack_override=ack)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    return IrrigationCommandResponse(
        command_id=f"cmd_{uuid4().hex[:8]}",
        zone_id=req.zone_id,
        status=CommandStatus.PENDING,
        timestamp=datetime.now(timezone.utc),
    )


async def _seed_admin_stub_prediction(req: IrrigationCommandRequest, request: Request) -> None:
    auth_context = getattr(request.state, "auth_context", {})
    if request.app.state.gateway_mode != "stub" or auth_context.get("role") != "admin":
        return
    if await request.app.state.prediction_cache.get_latest(req.zone_id) is not None:
        return
    prediction_request = PredictRequest(zone_id=req.zone_id, timestamp=datetime.now(timezone.utc))
    prediction = await request.app.state.ai_client.predict(prediction_request)
    await request.app.state.prediction_cache.store_success(prediction, "demo")
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
