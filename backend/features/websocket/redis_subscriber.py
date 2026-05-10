from __future__ import annotations

import asyncio
import json
import re

from pydantic import ValidationError

from features.websocket.manager import WebSocketManager
from features.websocket.schemas import RealtimeEvent

ZONE_CHANNEL_PATTERN = re.compile(r"^ws:zone:(?P<zone_id>[A-Z]\d{2})$")


class RedisSubscriber:
    def __init__(self, manager: WebSocketManager) -> None:
        self._manager = manager

    async def run_forever(self, redis_client: object) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("ws:broadcast", "system:alerts", "system:health")
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                await asyncio.sleep(0.1)
                continue
            channel = message.get("channel")
            data = message.get("data")
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if isinstance(channel, str) and isinstance(data, str):
                await self.dispatch_message(channel, data)

    async def dispatch_message(self, channel: str, message: str) -> bool:
        event = self._parse_event(message)
        if event is None:
            return False
        zone_match = ZONE_CHANNEL_PATTERN.match(channel)
        if zone_match:
            await self._manager.send_zone(zone_match.group("zone_id"), event)
            return True
        if channel in {"ws:broadcast", "system:alerts", "system:health"}:
            await self._manager.broadcast(event)
            return True
        return False

    def _parse_event(self, message: str) -> RealtimeEvent | None:
        try:
            payload = json.loads(message)
            return RealtimeEvent.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            return None
