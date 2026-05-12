from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RealtimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str
    payload: dict[str, Any]
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
