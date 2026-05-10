from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ImageryMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')

    zone_id: str
    scene_id: str | None = None
    cloud_cover: float | None = None
    acquisition_time: str | None = None
    stale: bool = True
    degraded: bool = False
    preview_url: str | None = None
    source: str = 'imagery-service'

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode='json')
