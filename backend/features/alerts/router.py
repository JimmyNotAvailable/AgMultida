from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.core.rate_limit import create_rate_limit_dependency
from backend.core.schemas import AlertRecord
from backend.features.websocket.schemas import RealtimeEvent

router = APIRouter(tags=["alerts"])


@router.post("/v1/alerts/{alert_id}/ack", response_model=AlertRecord, dependencies=[Depends(create_rate_limit_dependency("alerts"))])
async def acknowledge_alert(alert_id: str, request: Request):
    alert = await request.app.state.alert_service.acknowledge(alert_id)
    request.app.state.zone_status_cache.invalidate(alert.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(alert.zone_id)
    await request.app.state.websocket_manager.send_zone(
        alert.zone_id,
        RealtimeEvent(event="alert_acknowledged", payload={"zone_id": alert.zone_id, "alert_id": alert.alert_id}),
    )
    return alert
