from __future__ import annotations

import json
from collections import deque


class AlertStream:
    def __init__(self, redis_client: object | None = None, key: str = "alerts:events") -> None:
        self._redis_client = redis_client
        self._key = key
        self._entries: deque[dict] = deque(maxlen=256)

    async def append(self, payload: dict) -> None:
        self._entries.append(payload)
        if self._redis_client is None:
            return
        try:
            await self._redis_client.xadd(self._key, {"payload": json.dumps(payload, separators=(",", ":"))})
        except Exception:
            return
