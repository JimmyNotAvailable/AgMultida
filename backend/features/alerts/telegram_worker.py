from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx


@dataclass(frozen=True)
class TelegramWorkerConfig:
    enabled: bool
    bot_token: str
    chat_id: str
    api_base_url: str = "https://api.telegram.org"
    consumer_group: str = "alert-monitor"
    consumer_name: str = "gateway-1"
    stream_key: str = "alerts:events"
    dlq_key: str = "alerts:dlq"
    max_retries: int = 3
    block_ms: int = 1000
    backoff_base_seconds: float = 1.0

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class TelegramWorker:
    def __init__(
        self,
        redis_client: object,
        config: TelegramWorkerConfig,
        *,
        send_message: Callable[[str], Awaitable[str]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.random() * 0.25,
    ) -> None:
        self._redis = redis_client
        self._config = config
        self._sleep = sleep
        self._jitter = jitter
        self._send_message = send_message or self._build_sender()

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(self._config.stream_key, self._config.consumer_group, id="0", mkstream=True)
        except Exception:
            return

    async def run_forever(self) -> None:
        while True:
            await self.run_once()

    async def run_once(self) -> None:
        await self.ensure_group()
        records = await self._redis.xreadgroup(
            self._config.consumer_group,
            self._config.consumer_name,
            {self._config.stream_key: ">"},
            count=1,
            block=self._config.block_ms,
        )
        if not records:
            return
        for stream_key, entries in records:
            for entry_id, fields in entries:
                payload = self._parse_payload(fields)
                if payload is None:
                    await self._ack(stream_key, entry_id)
                    continue
                if not self._should_send(payload):
                    await self._ack(stream_key, entry_id)
                    continue
                error = await self._dispatch(payload)
                if error is None:
                    await self._ack(stream_key, entry_id)
                    continue
                await self._send_to_dlq(payload, error)
                await self._ack(stream_key, entry_id)

    async def _dispatch(self, payload: dict) -> str | None:
        for attempt in range(1, self._config.max_retries + 1):
            try:
                message_id = await self._send_message(self._format_message(payload))
                await self._mark_sent(payload, message_id)
                return None
            except Exception as exc:
                if attempt >= self._config.max_retries:
                    return str(exc)
                delay = (self._config.backoff_base_seconds * (2 ** (attempt - 1))) + self._jitter()
                await self._sleep(delay)
        return "unreachable"

    def _should_send(self, payload: dict) -> bool:
        if payload.get("status") != "open":
            return False
        if payload.get("telegram_sent"):
            return False
        return payload.get("severity") in {"moderate", "critical"}

    def _parse_payload(self, fields: dict[str, str]) -> dict | None:
        raw = fields.get("payload")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _format_message(self, payload: dict) -> str:
        return f"[{payload['severity']}] {payload['zone_id']}: {payload['message']}"

    async def _mark_sent(self, payload: dict, message_id: str) -> None:
        payload["telegram_sent"] = True
        payload["telegram_msg_id"] = message_id
        await self._redis.hset(f"alert:{payload['alert_id']}", {"payload": json.dumps(payload)})

    async def _send_to_dlq(self, payload: dict, last_error: str) -> None:
        body = {**payload, "retry_count": self._config.max_retries, "last_error": last_error}
        await self._redis.xadd(self._config.dlq_key, {"payload": json.dumps(body)})

    async def _ack(self, stream_key: str, entry_id: str) -> None:
        await self._redis.xack(stream_key, self._config.consumer_group, entry_id)

    def _build_sender(self) -> Callable[[str], Awaitable[str]]:
        async def send(text: str) -> str:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    f"{self._config.api_base_url}/bot{self._config.bot_token}/sendMessage",
                    json={"chat_id": self._config.chat_id, "text": text},
                )
                response.raise_for_status()
                body = response.json()
                return str(body["result"]["message_id"])

        return send
