from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from api_gateway.main import app
from core.config import get_settings
from features.alerts.telegram_worker import TelegramWorker, TelegramWorkerConfig


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {"alerts:events": []}
        self.acked: list[tuple[str, str, str]] = []
        self.groups: list[tuple[str, str, str]] = []

    async def xgroup_create(self, name: str, groupname: str, id: str = "0", mkstream: bool = False) -> None:
        self.groups.append((name, groupname, id))

    async def xreadgroup(self, groupname: str, consumername: str, streams: dict[str, str], count: int = 1, block: int = 1000):
        key = next(iter(streams))
        if not self.streams.get(key):
            return []
        entry = self.streams[key].pop(0)
        return [(key, [entry])]

    async def xack(self, key: str, group: str, entry_id: str) -> None:
        self.acked.append((key, group, entry_id))

    async def xadd(self, key: str, fields: dict[str, str]) -> None:
        self.streams.setdefault(key, []).append((f"{len(self.streams.get(key, [])) + 1}-0", fields))

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes.get(key, {}).get(field)

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes[key] = {**self.hashes.get(key, {}), **mapping}


def alert_payload(**overrides) -> dict:
    payload = {
        "event": "alert_created",
        "alert_id": "alert-1",
        "zone_id": "A01",
        "rule_id": "irrigation_action",
        "severity": "moderate",
        "status": "open",
        "message": "Recommended action: moderate",
        "telegram_sent": False,
    }
    payload.update(overrides)
    return payload


def seed(redis: FakeRedis, payload: dict) -> None:
    redis.streams["alerts:events"].append(("1-0", {"payload": json.dumps(payload)}))
    redis.hashes[f"alert:{payload['alert_id']}"] = {"payload": json.dumps(payload)}


def config() -> TelegramWorkerConfig:
    return TelegramWorkerConfig(enabled=True, bot_token="token", chat_id="chat")


def test_successful_push_updates_telegram_state() -> None:
    async def run() -> None:
        redis = FakeRedis()
        seed(redis, alert_payload())
        sent: list[str] = []

        async def send(text: str) -> str:
            sent.append(text)
            return "msg-1"

        worker = TelegramWorker(redis, config(), send_message=send)
        await worker.run_once()
        payload = json.loads(redis.hashes["alert:alert-1"]["payload"])
        assert sent == ["[moderate] A01: Recommended action: moderate"]
        assert payload["telegram_sent"] is True
        assert payload["telegram_msg_id"] == "msg-1"
        assert redis.acked == [("alerts:events", "alert-monitor", "1-0")]

    anyio.run(run)


def test_duplicate_sent_alert_is_skipped_on_restart() -> None:
    async def run() -> None:
        redis = FakeRedis()
        seed(redis, alert_payload(telegram_sent=True, telegram_msg_id="msg-1"))
        calls = 0

        async def send(text: str) -> str:
            nonlocal calls
            calls += 1
            return "msg-2"

        worker = TelegramWorker(redis, config(), send_message=send)
        await worker.run_once()
        assert calls == 0
        assert redis.acked == [("alerts:events", "alert-monitor", "1-0")]

    anyio.run(run)


def test_non_open_or_low_severity_alert_is_skipped() -> None:
    async def run() -> None:
        redis = FakeRedis()
        seed(redis, alert_payload(status="acknowledged", severity="critical"))
        calls = 0

        async def send(text: str) -> str:
            nonlocal calls
            calls += 1
            return "msg-1"

        worker = TelegramWorker(redis, config(), send_message=send)
        await worker.run_once()
        assert calls == 0
        assert redis.acked == [("alerts:events", "alert-monitor", "1-0")]

    anyio.run(run)


def test_failed_http_retries_then_routes_to_dlq() -> None:
    async def run() -> None:
        redis = FakeRedis()
        seed(redis, alert_payload(alert_id="alert-fail"))
        sleeps: list[float] = []
        calls = 0

        async def send(text: str) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("telegram down")

        async def sleep(delay: float) -> None:
            sleeps.append(delay)

        worker = TelegramWorker(redis, config(), send_message=send, sleep=sleep, jitter=lambda: 0.0)
        await worker.run_once()
        assert calls == 3
        assert sleeps == [1.0, 2.0]
        dlq = redis.streams["alerts:dlq"][0][1]
        dlq_payload = json.loads(dlq["payload"])
        assert dlq_payload["alert_id"] == "alert-fail"
        assert dlq_payload["retry_count"] == 3
        assert "telegram down" in dlq_payload["last_error"]
        assert redis.acked == [("alerts:events", "alert-monitor", "1-0")]

    anyio.run(run)


def test_missing_config_guard_degrades_readyz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALERT_TELEGRAM_ENABLED", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/v1/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["telegram"]["status"] == "degraded"
    get_settings.cache_clear()
