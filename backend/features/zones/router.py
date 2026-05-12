from __future__ import annotations

from fastapi import APIRouter, Depends, Path as RoutePath, Query, Request

from backend.core.errors import AgTechError, ErrorCode
from backend.core.imagery import get_latest_zone_imagery_for_api, get_zone_imagery_history_for_api
from backend.core.rate_limit import create_rate_limit_dependency
from backend.core.schemas import AlertFeedResponse, ImageryScene, ImagerySceneCollection, ZoneStatusResponse
from backend.core.security import require_role
from backend.core.weather import ZoneWeatherResponse
from backend.features.imagery.agromonitoring import get_zone_spectral
from backend.features.zones.loader import load_zone_feature
from backend.features.zones.registry import ZoneRegistryService
from backend.features.zones.schemas import ZoneRegistryResponse
from backend.features.zones.status_builder import build_zone_status
from backend.features.zones.weather import fetch_weather_for_zone

router = APIRouter(prefix="/v1/zones", tags=["zones"])
zone_read_limit_dependency = Depends(create_rate_limit_dependency("zones"))
ADMIN_READ_DEPENDENCIES = [Depends(require_role("viewer", "operator", "admin")), zone_read_limit_dependency]
ZONE_ID_PATTERN = r"^[A-Z]\d{2}$"


@router.get("", response_model=ZoneRegistryResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def list_zones(request: Request) -> ZoneRegistryResponse:
    service: ZoneRegistryService = request.app.state.zone_registry_service
    return ZoneRegistryResponse(zones=await service.list_zones())


@router.get("/{zone_id}/weather/latest", response_model=ZoneWeatherResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_weather_latest(zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN)):
    zone_feature = load_zone_feature(zone_id)
    return await fetch_weather_for_zone(zone_id, zone_feature["geometry"]["coordinates"][0])


@router.get("/{zone_id}/status", response_model=ZoneStatusResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_status(request: Request, zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN)):
    async def build_base_status() -> ZoneStatusResponse:
        zone_feature = load_zone_feature(zone_id)
        weather = await fetch_weather_for_zone(zone_id, zone_feature["geometry"]["coordinates"][0])
        return build_zone_status(zone_id=zone_id, weather=weather)

    status = await request.app.state.zone_status_aggregate.get_or_build(zone_id, build_base_status)
    return request.app.state.zone_status_cache.set(zone_id, status)


@router.get("/{zone_id}/imagery/latest", response_model=ImageryScene, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_imagery_latest(zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN)):
    zone_feature = load_zone_feature(zone_id)
    return await get_latest_zone_imagery_for_api(zone_id, zone_feature["geometry"]["coordinates"][0])


@router.get("/{zone_id}/imagery/history", response_model=ImagerySceneCollection, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_imagery_history(
    zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN),
    limit: int = Query(default=10, ge=1, le=10),
):
    zone_feature = load_zone_feature(zone_id)
    return await get_zone_imagery_history_for_api(zone_id, zone_feature["geometry"]["coordinates"][0], limit=limit)


@router.get("/{zone_id}/spectral/latest", dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_spectral_latest(zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN)):
    return await get_zone_spectral(zone_id)


@router.get("/{zone_id}/alerts", response_model=AlertFeedResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_alerts(
    request: Request,
    zone_id: str = RoutePath(pattern=ZONE_ID_PATTERN),
    severity: list[str] | None = Query(default=None),
    acknowledged: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    if severity is not None:
        invalid = [value for value in severity if value not in {"critical", "moderate", "watch", "warning", "info", "degraded"}]
        if invalid:
            raise AgTechError(
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Invalid severity filter",
                status_code=422,
                details={"severity": invalid},
            )
    alerts = await request.app.state.alert_service.list_zone_alerts(zone_id, limit=limit)
    if severity is not None:
        selected = set(severity)
        alerts = [alert for alert in alerts if alert.severity in selected]
    if acknowledged is not None:
        alerts = [alert for alert in alerts if alert.acknowledged is acknowledged]
    return AlertFeedResponse(zone_id=zone_id, alerts=alerts[:limit])
