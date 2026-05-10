from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from features.websocket.schemas import RealtimeEvent


@dataclass
class WebSocketConnection:
    socket: Any
    zones: set[str] = field(default_factory=set)


class WebSocketManager:
    def __init__(self, heartbeat_seconds: float = 30.0) -> None:
        self._connections: dict[Any, WebSocketConnection] = {}
        self._heartbeat_seconds = heartbeat_seconds

    async def connect(self, socket: Any, *, zones: set[str] | None = None) -> None:
        selected_zones = set(zones or set())
        self._connections[socket] = WebSocketConnection(socket=socket, zones=selected_zones)
        await socket.send_json(
            RealtimeEvent(
                event="subscription_ack",
                payload={"zones": sorted(selected_zones)},
            ).model_dump(mode="json")
        )

    def disconnect(self, socket: Any) -> None:
        self._connections.pop(socket, None)

    async def broadcast(self, event: RealtimeEvent) -> None:
        await self._send_to(list(self._connections.values()), event)

    async def send_zone(self, zone_id: str, event: RealtimeEvent) -> None:
        targets = [connection for connection in self._connections.values() if zone_id in connection.zones]
        await self._send_to(targets, event)

    async def heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_seconds)
            await self.broadcast(RealtimeEvent(event="ping", payload={}))

    async def _send_to(self, connections: list[WebSocketConnection], event: RealtimeEvent) -> None:
        payload = event.model_dump(mode="json")
        for connection in connections:
            try:
                await connection.socket.send_json(payload)
            except Exception:
                self.disconnect(connection.socket)
