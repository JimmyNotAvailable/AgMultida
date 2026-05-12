from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PredictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    timestamp: datetime
    stress_prob: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    degraded_mode: bool
    attention_weights: list[float] = Field(default_factory=list)
    modality_mask: Optional[list[float]] = None
    model_version: Optional[str] = None
