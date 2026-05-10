from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from core.schemas import ZoneRegistryEntry


class ZoneBounds(BaseModel):
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float


class ZoneRegistryItem(BaseModel):
    zone: ZoneRegistryEntry
    bounds: ZoneBounds
    centroid: tuple[float, float]


class ZoneRegistryResponse(BaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    zones: list[ZoneRegistryItem]
