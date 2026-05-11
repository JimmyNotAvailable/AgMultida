from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-32b")

from backend.features.websocket.manager import WebSocketManager
from backend.features.websocket.redis_subscriber import RedisSubscriber
from backend.features.websocket.schemas import RealtimeEvent


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def test_manager_connect_returns_subscription_ack_with_zones() -> None:
    async def run() -> None:
        manager = WebSocketManager()
        socket = FakeSocket()
        await manager.connect(socket, zones={"A01", "A02"})
        assert socket.sent[0]["event"] == "subscription_ack"
        assert socket.sent[0]["payload"]["zones"] == ["A01", "A02"]

    anyio.run(run)


def test_manager_zone_fanout_targets_only_subscribed_clients() -> None:
    async def run() -> None:
        manager = WebSocketManager()
        a01 = FakeSocket()
        b07 = FakeSocket()
        await manager.connect(a01, zones={"A01"})
        await manager.connect(b07, zones={"B07"})
        await manager.send_zone("A01", RealtimeEvent(event="prediction_completed", payload={"zone_id": "A01"}))
        assert a01.sent[-1]["event"] == "prediction_completed"
        assert len(b07.sent) == 1

    anyio.run(run)


def test_subscriber_parses_strict_event_and_dispatches_zone() -> None:
    async def run() -> None:
        manager = WebSocketManager()
        socket = FakeSocket()
        await manager.connect(socket, zones={"A01"})
        subscriber = RedisSubscriber(manager)
        await subscriber.dispatch_message("ws:zone:A01", json.dumps({"event": "alert_opened", "payload": {"zone_id": "A01"}, "ts": "2026-05-10T00:00:00Z", "trace_id": "trace-1"}))
        assert socket.sent[-1]["event"] == "alert_opened"

    anyio.run(run)


def test_subscriber_rejects_arbitrary_event_fields() -> None:
    async def run() -> None:
        manager = WebSocketManager()
        subscriber = RedisSubscriber(manager)
        result = await subscriber.dispatch_message("ws:broadcast", json.dumps({"event": "status_changed", "payload": {}, "ts": "2026-05-10T00:00:00Z", "trace_id": "trace-1", "extra": "bad"}))
        assert result is False

    anyio.run(run)
