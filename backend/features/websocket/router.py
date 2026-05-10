from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from backend.core.errors import AgTechError
from backend.core.rate_limit import check_rate_limit
from backend.features.websocket.auth import authenticate_websocket, is_allowed_ws_origin, parse_ws_zones

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    try:
        if not is_allowed_ws_origin(websocket):
            await websocket.close(code=1008, reason="Origin not allowed")
            return
        payload = authenticate_websocket(websocket)
        websocket.state.auth_context = payload
        check_rate_limit("ws-handshake", payload.get("sub", "anonymous"))
        await websocket.accept()
        zones = parse_ws_zones(websocket)
        await websocket.app.state.websocket_manager.connect(websocket, zones=zones)
        while True:
            check_rate_limit("ws-message", payload.get("sub", "anonymous"))
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if message.get("event") == "subscribe":
                requested = message.get("payload", {}).get("zones", [])
                zones = {zone for zone in requested if isinstance(zone, str) and len(zone) == 3}
                await websocket.app.state.websocket_manager.connect(websocket, zones=zones)
    except AgTechError as exc:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1008, reason=exc.message)
    except WebSocketDisconnect:
        websocket.app.state.websocket_manager.disconnect(websocket)
