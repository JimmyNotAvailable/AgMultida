from __future__ import annotations

from fastapi import APIRouter, Request

from core.schemas import AlertRecord

router = APIRouter(tags=["alerts"])


@router.post("/v1/alerts/{alert_id}/ack", response_model=AlertRecord)
async def acknowledge_alert(alert_id: str, request: Request):
    alert = await request.app.state.alert_service.acknowledge(alert_id)
    request.app.state.zone_status_cache.invalidate(alert.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(alert.zone_id)
    return alert
