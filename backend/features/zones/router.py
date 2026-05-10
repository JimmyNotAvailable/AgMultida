from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.rate_limit import create_rate_limit_dependency
from core.security import require_role
from features.zones.registry import ZoneRegistryService
from features.zones.schemas import ZoneRegistryResponse

router = APIRouter(prefix="/v1/zones", tags=["zones"])
zone_read_limit_dependency = Depends(create_rate_limit_dependency("zones"))


@router.get("", response_model=ZoneRegistryResponse, dependencies=[Depends(require_role("viewer", "operator", "admin")), zone_read_limit_dependency])
async def list_zones(request: Request) -> ZoneRegistryResponse:
    service: ZoneRegistryService = request.app.state.zone_registry_service
    return ZoneRegistryResponse(zones=await service.list_zones())
