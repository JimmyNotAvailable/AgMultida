from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class CircuitBreakerState:
    state: str = 'closed'
    failure_count: int = 0
    opened_at: str | None = None


class CircuitBreaker:
    def __init__(self, key: str, redis_client: object | None = None, failure_threshold: int = 3, cooldown_seconds: int = 60) -> None:
        self._key = key
        self._redis_client = redis_client
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._memory = CircuitBreakerState()

    async def current_state(self) -> str:
        state = await self._load()
        if state.state != 'open' or state.opened_at is None:
            return state.state
        opened_at = datetime.fromisoformat(state.opened_at)
        if datetime.now(timezone.utc) >= opened_at + timedelta(seconds=self._cooldown_seconds):
            half_open = CircuitBreakerState(state='half-open', failure_count=state.failure_count, opened_at=state.opened_at)
            await self._save(half_open)
            return half_open.state
        return state.state

    async def allow_request(self) -> bool:
        return await self.current_state() != 'open'

    async def record_failure(self) -> None:
        state = await self._load()
        next_count = state.failure_count + 1
        if next_count >= self._failure_threshold:
            await self._save(CircuitBreakerState(state='open', failure_count=next_count, opened_at=datetime.now(timezone.utc).isoformat()))
            return
        await self._save(CircuitBreakerState(state=state.state, failure_count=next_count, opened_at=state.opened_at))

    async def record_success(self) -> None:
        await self._save(CircuitBreakerState())

    async def _load(self) -> CircuitBreakerState:
        if self._redis_client is None:
            return self._memory
        raw = await self._redis_client.get(self._key)
        if not raw:
            return self._memory
        payload = json.loads(raw)
        self._memory = CircuitBreakerState(**payload)
        return self._memory

    async def _save(self, state: CircuitBreakerState) -> None:
        self._memory = state
        if self._redis_client is None:
            return
        await self._redis_client.set(self._key, json.dumps(state.__dict__), ex=self._cooldown_seconds)
