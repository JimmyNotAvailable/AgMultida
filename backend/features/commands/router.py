from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Query, Request

from backend.core.schemas import CommandStatus, IrrigationCommandRequest, IrrigationCommandResponse

router = APIRouter(tags=["commands"])


@router.post("/v1/commands", response_model=IrrigationCommandResponse)
async def create_command(req: IrrigationCommandRequest, request: Request, ack: bool = Query(default=False)):
    await request.app.state.command_safety_service.ensure_allowed(req, ack_override=ack)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    return IrrigationCommandResponse(
        command_id=f"cmd_{uuid4().hex[:8]}",
        zone_id=req.zone_id,
        status=CommandStatus.PENDING,
        timestamp=datetime.now(timezone.utc),
    )
