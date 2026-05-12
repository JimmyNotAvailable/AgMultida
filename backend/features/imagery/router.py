from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.core.errors import AgTechError, ErrorCode
from backend.core.imagery import get_scene_for_preview
from backend.core.imagery_proxy import build_preview_cache_headers, build_preview_png
from backend.core.rate_limit import create_rate_limit_dependency
from backend.features.zones.loader import get_zone_bbox

router = APIRouter(tags=["imagery"])


@router.get("/v1/imagery/preview/{scene_id}", dependencies=[Depends(create_rate_limit_dependency("imagery_preview"))])
async def imagery_preview(
    scene_id: str,
    mode: str = Query(default="rgb", pattern="^(rgb|ndvi)$"),
):
    scene = await get_scene_for_preview(scene_id)
    if scene is None:
        raise AgTechError(
            error_code=ErrorCode.ZONE_NOT_FOUND,
            message="Scene not found",
            status_code=404,
            details={"scene_id": scene_id},
        )
    bbox = get_zone_bbox(scene.zone_id)
    preview = await build_preview_png(scene, bbox, mode)
    headers = build_preview_cache_headers()
    headers["X-Preview-Source"] = "rendered" if preview.generated_from_source else "placeholder"
    return StreamingResponse(
        content=iter([preview.content]),
        media_type="image/png",
        headers=headers,
    )
