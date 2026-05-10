from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"event": "subscription_ack", "payload": {"zones": []}, "ts": "1970-01-01T00:00:00Z", "trace_id": "stub"})
