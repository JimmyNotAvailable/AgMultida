"""API Gateway: central REST + WebSocket entry point."""
from __future__ import annotations

import csv
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, Path as RoutePath, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocketState

from api_gateway.clients.ai_client import LiveAIClient, StubAIClient
from api_gateway.clients.decision_client import LiveDecisionClient, StubDecisionClient
from api_gateway.clients.ingestion_client import LiveIngestionClient, StubIngestionClient
from decision_engine.alert_engine import AlertEvaluationInput, AlertRepository, evaluate_alerts
from core.config import get_settings
from core.db import check_database_ready, close_db_pool, open_db_pool
from core.errors import AgTechError, ErrorCode, mask_internal_exception
from core.geospatial import calculate_centroid
from core.imagery import get_latest_zone_imagery_for_api, get_scene_for_preview, get_zone_imagery_history_for_api
from core.imagery_proxy import build_preview_cache_headers, build_preview_png
from core.rate_limit import check_rate_limit, create_rate_limit_dependency, reset_rate_limiter_backend
from core.schemas import (
    AlertFeedResponse,
    AlertRecord,
    AlertSummary,
    CommandStatus,
    ConfidenceFlag,
    HealthResponse,
    ImageryScene,
    ImagerySceneCollection,
    ImagerySummary,
    IrrigationCommandRequest,
    IrrigationCommandResponse,
    IrrigationDecision,
    PredictRequest,
    PredictResponse,
    RecommendRequest,
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    ZoneListItemResponse,
    ZoneListResponse,
    ZoneRegistryEntry,
    ZoneStatusResponse,
)
from core.security import decode_access_token, require_role
from core.weather import ZoneWeatherResponse
from core.zone_status_cache import InMemoryZoneStatusCache

admin_read_dependency = Depends(require_role("viewer", "operator", "admin"))
admin_write_dependency = Depends(require_role("operator", "admin"))
admin_mutation_dependency = Depends(create_rate_limit_dependency("admin"))
zone_read_limit_dependency = Depends(create_rate_limit_dependency("zones"))

ADMIN_READ_DEPENDENCIES = [admin_read_dependency, zone_read_limit_dependency]
ADMIN_WRITE_DEPENDENCIES = [admin_write_dependency, admin_mutation_dependency]


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    if settings.GATEWAY_MODE == "live" and not settings.AI_SERVING_URL:
        raise RuntimeError("AI_SERVING_URL must be set when GATEWAY_MODE=live")

    if settings.GATEWAY_MODE == "live":
        from core.http_client import create_http_client

        ai_http = create_http_client(
            base_url=settings.AI_SERVING_URL,
            timeout_ms=settings.AI_SERVING_TIMEOUT_MS,
        )
        ingestion_http = create_http_client(
            base_url=settings.INGESTION_SERVICE_URL,
            timeout_ms=settings.INGESTION_SERVICE_TIMEOUT_MS,
        )
        application.state.ai_client = LiveAIClient(
            ai_http,
            internal_api_key=settings.INTERNAL_API_KEY,
            header_name=settings.INTERNAL_API_KEY_HEADER,
        )
        application.state.ingestion_client = LiveIngestionClient(
            ingestion_http,
            internal_api_key=settings.INTERNAL_API_KEY,
            header_name=settings.INTERNAL_API_KEY_HEADER,
        )
        application.state.decision_client = LiveDecisionClient()
    else:
        application.state.ai_client = StubAIClient()
        application.state.ingestion_client = StubIngestionClient()
        application.state.decision_client = StubDecisionClient()

    reset_rate_limiter_backend()

    try:
        await open_db_pool()
    except RuntimeError:
        application.state.db_enabled = False
    else:
        application.state.db_enabled = True

    application.state.gateway_mode = settings.GATEWAY_MODE
    application.state.zone_status_cache = InMemoryZoneStatusCache(settings.ZONE_STATUS_CACHE_TTL_SECONDS)
    application.state.alert_repository = AlertRepository()
    yield

    if hasattr(application.state, "ai_client") and hasattr(application.state.ai_client, "close"):
        await application.state.ai_client.close()
    if hasattr(application.state, "ingestion_client") and hasattr(application.state.ingestion_client, "close"):
        await application.state.ingestion_client.close()
    application.state.ai_client = StubAIClient()
    application.state.ingestion_client = StubIngestionClient()
    application.state.decision_client = StubDecisionClient()
    application.state.gateway_mode = "stub"
    await close_db_pool()


app = FastAPI(title="AgMultida API Gateway", version="1.0.0", lifespan=lifespan)
app.state.ai_client = StubAIClient()
app.state.ingestion_client = StubIngestionClient()
app.state.decision_client = StubDecisionClient()
app.state.gateway_mode = "stub"
app.state.db_enabled = False
app.state.zone_status_cache = InMemoryZoneStatusCache(get_settings().ZONE_STATUS_CACHE_TTL_SECONDS)
app.state.alert_repository = AlertRepository()

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.INTERNAL_API_KEY_HEADER],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.TRUSTED_HOSTS))

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZONE_REGISTRY_PATH = PROJECT_ROOT / "metadata" / "zone_registry.csv"
ZONE_GEOJSON_PATH = PROJECT_ROOT / "metadata" / "zones.geojson"


@app.exception_handler(AgTechError)
async def agtech_error_handler(request: Request, exc: AgTechError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump(mode="json"))


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    resp = mask_internal_exception(exc)
    return JSONResponse(status_code=500, content=resp.model_dump(mode="json"))


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if get_settings().ENABLE_HSTS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def extract_ws_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def is_allowed_ws_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    return origin in get_settings().CORS_ORIGINS


def authenticate_websocket(websocket: WebSocket) -> dict:
    settings = get_settings()
    if not settings.WS_REQUIRE_AUTH:
        return {"sub": "dev-ws-bypass", "role": "viewer"}
    token = extract_ws_token(websocket)
    if not token:
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_TOKEN,
            message="Missing bearer token",
            status_code=401,
        )
    payload = decode_access_token(token)
    if payload.get("role") not in {"viewer", "operator", "admin"}:
        raise AgTechError(
            error_code=ErrorCode.AUTH_INSUFFICIENT_ROLE,
            message="Insufficient role",
            status_code=403,
        )
    return payload


@app.get("/v1/healthz", response_model=HealthResponse)
async def healthz():
    return HealthResponse()


@app.get("/v1/readyz")
async def readyz(request: Request):
    mode = getattr(request.app.state, "gateway_mode", "unknown")
    checked_at = datetime.now(timezone.utc).isoformat()
    decision_dep = {"status": "stub"} if mode == "stub" else {"status": "in_process", "checked_at": checked_at}
    database_dep = {"status": "disabled"}
    if request.app.state.db_enabled:
        database = await check_database_ready()
        database_dep = {
            "status": database["status"],
            "checked_at": checked_at,
            "details": database["details"],
        }

    if mode == "stub":
        overall = "ok" if database_dep["status"] in {"ok", "disabled"} else "degraded"
        return {
            "status": overall,
            "mode": mode,
            "dependencies": {
                "database": database_dep,
                "ai_serving": {"status": "stub", "checked_at": checked_at},
                "ingestion_service": {"status": "stub", "checked_at": checked_at},
                "decision_engine": decision_dep,
            },
        }

    ai_ready = await request.app.state.ai_client.ready()
    ingestion_ready = await request.app.state.ingestion_client.ready()
    ai_dep = {
        "status": ai_ready.get("status", "degraded"),
        "checked_at": checked_at,
        "model_loaded": ai_ready.get("model_loaded"),
        "manifest_loaded": ai_ready.get("manifest_loaded"),
        "upstream_last_error": "Dependency unavailable" if ai_ready.get("upstream_last_error") else None,
    }
    ingestion_dep = {
        "status": ingestion_ready.get("status", "degraded"),
        "checked_at": checked_at,
        "database": ingestion_ready.get("database"),
    }
    gateway_status = "ok" if ai_dep["status"] == "ok" and database_dep["status"] in {"ok", "disabled"} else "degraded"
    return {
        "status": gateway_status,
        "mode": mode,
        "dependencies": {
            "database": database_dep,
            "ai_serving": ai_dep,
            "ingestion_service": ingestion_dep,
            "decision_engine": decision_dep,
        },
    }


@app.post("/v1/predict", response_model=PredictResponse, dependencies=ADMIN_WRITE_DEPENDENCIES)
async def predict(req: PredictRequest, request: Request):
    prediction = await request.app.state.ai_client.predict(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    return prediction


@app.post("/v1/recommend", response_model=IrrigationDecision, dependencies=ADMIN_WRITE_DEPENDENCIES)
async def recommend(req: RecommendRequest, request: Request):
    decision = request.app.state.decision_client.recommend(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    return decision


@app.post("/v1/telemetry", response_model=TelemetryIngestResponse, dependencies=ADMIN_WRITE_DEPENDENCIES)
async def ingest_telemetry(req: TelemetryIngestRequest, request: Request):
    response = await request.app.state.ingestion_client.ingest(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    return response


@app.post("/v1/commands", response_model=IrrigationCommandResponse, dependencies=ADMIN_WRITE_DEPENDENCIES)
async def create_command(req: IrrigationCommandRequest, request: Request):
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    return IrrigationCommandResponse(
        command_id=f"cmd_{uuid4().hex[:8]}",
        zone_id=req.zone_id,
        status=CommandStatus.PENDING,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/v1/zones", response_model=ZoneListResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def list_zones():
    checked_at = datetime.now(timezone.utc)
    return ZoneListResponse(
        zones=[
            ZoneListItemResponse(
                zone=entry,
                command_state=None,
                confidence_flag=None,
                degraded_mode=None,
                updated_at=checked_at,
            )
            for entry in load_zone_registry()
        ],
    )


@app.get("/v1/zones/{zone_id}/weather/latest", response_model=ZoneWeatherResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_weather_latest(zone_id: str = RoutePath(pattern=r"^[A-Z]\d{2}$")):
    zone_feature = load_zone_feature(zone_id)
    weather = await fetch_weather_for_zone(zone_id, zone_feature["geometry"]["coordinates"][0])
    return weather


@app.get("/v1/zones/{zone_id}/status", response_model=ZoneStatusResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_status(request: Request, zone_id: str = RoutePath(pattern=r"^[A-Z]\d{2}$")):
    cached = request.app.state.zone_status_cache.get(zone_id)
    if cached is not None:
        return cached

    zone_feature = load_zone_feature(zone_id)
    weather = await fetch_weather_for_zone(zone_id, zone_feature["geometry"]["coordinates"][0])
    status = build_zone_status(zone_id=zone_id, weather=weather)
    return request.app.state.zone_status_cache.set(zone_id, status)


@app.get("/v1/zones/{zone_id}/imagery/latest", response_model=ImageryScene, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_imagery_latest(zone_id: str = RoutePath(pattern=r"^[A-Z]\d{2}$")):
    zone_feature = load_zone_feature(zone_id)
    return await get_latest_zone_imagery_for_api(zone_id, zone_feature["geometry"]["coordinates"][0])


@app.get("/v1/zones/{zone_id}/imagery/history", response_model=ImagerySceneCollection, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_imagery_history(
    zone_id: str = RoutePath(pattern=r"^[A-Z]\d{2}$"),
    limit: int = Query(default=10, ge=1, le=10),
):
    zone_feature = load_zone_feature(zone_id)
    return await get_zone_imagery_history_for_api(zone_id, zone_feature["geometry"]["coordinates"][0], limit=limit)


@app.get("/v1/imagery/preview/{scene_id}", dependencies=ADMIN_READ_DEPENDENCIES)
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


@app.get("/v1/zones/{zone_id}/alerts", response_model=AlertFeedResponse, dependencies=ADMIN_READ_DEPENDENCIES)
async def zone_alerts(
    zone_id: str = RoutePath(pattern=r"^[A-Z]\d{2}$"),
    severity: list[str] | None = Query(default=None),
    acknowledged: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    load_zone_feature(zone_id)
    if severity is not None:
        invalid = [value for value in severity if value not in {"critical", "warning", "info", "degraded"}]
        if invalid:
            raise AgTechError(
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Invalid severity filter",
                status_code=422,
                details={"severity": invalid},
            )
    now = datetime.now(timezone.utc)
    alerts = build_zone_alert_records(zone_id, now, repository=app.state.alert_repository)
    if severity is not None:
        selected = set(severity)
        alerts = [alert for alert in alerts if alert.severity in selected]
    if acknowledged is not None:
        alerts = [alert for alert in alerts if alert.acknowledged is acknowledged]
    return AlertFeedResponse(zone_id=zone_id, alerts=alerts[:limit])


def load_zone_registry() -> list[ZoneRegistryEntry]:
    with ZONE_REGISTRY_PATH.open(newline="", encoding="utf-8") as registry_file:
        return [
            ZoneRegistryEntry(
                zone_id=row["zone_id"],
                zone_name=row["zone_name"],
                province=row["province"],
                crop_type=row["crop_type"],
                split=row["split"],
                local_timezone=row["local_timezone"],
            )
            for row in csv.DictReader(registry_file)
        ]


def load_zone_feature(zone_id: str) -> dict:
    with ZONE_GEOJSON_PATH.open(encoding="utf-8") as geojson_file:
        payload = json.load(geojson_file)
    for feature in payload.get("features", []):
        if feature.get("properties", {}).get("zone_id") == zone_id:
            return feature
    raise AgTechError(
        error_code=ErrorCode.ZONE_NOT_FOUND,
        message="Zone not found",
        status_code=404,
        details={"zone_id": zone_id},
    )


def get_zone_bbox(zone_id: str) -> tuple[float, float, float, float]:
    feature = load_zone_feature(zone_id)
    coordinates = feature["geometry"]["coordinates"][0]
    longitudes = [point[0] for point in coordinates]
    latitudes = [point[1] for point in coordinates]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


async def fetch_weather_for_zone(zone_id: str, polygon: list[list[float]]) -> ZoneWeatherResponse:
    latitude, longitude = calculate_centroid(polygon)
    settings = get_settings()
    timeout = httpx.Timeout(settings.WEATHER_TIMEOUT_MS / 1000)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation",
        "forecast_days": 3,
        "timezone": "UTC",
    }

    try:
        async with httpx.AsyncClient(base_url=settings.WEATHER_API_BASE_URL, timeout=timeout) as client:
            response = await client.get("/forecast", params=params)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message="Weather service unavailable",
            status_code=502,
            details={"service": "open-meteo", "zone_id": zone_id},
        ) from exc

    current_raw = body.get("current", {})
    current = {
        "time": current_raw.get("time"),
        "temperature_2m": current_raw.get("temperature_2m"),
        "relative_humidity_2m": current_raw.get("relative_humidity_2m"),
        "precipitation": current_raw.get("precipitation"),
        "wind_speed_10m": current_raw.get("wind_speed_10m"),
    }
    hourly = body.get("hourly", {})
    return ZoneWeatherResponse.model_validate(
        {
            "zone_id": zone_id,
            "latitude": latitude,
            "longitude": longitude,
            "current": current if current.get("time") else None,
            "hourly": {
                "time": hourly.get("time", []),
                "temperature_2m": hourly.get("temperature_2m", []),
                "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
                "precipitation_probability": hourly.get("precipitation_probability", []),
                "precipitation": hourly.get("precipitation", []),
            },
            "updated_at": datetime.now(timezone.utc),
        }
    )


def build_zone_status(zone_id: str, weather: ZoneWeatherResponse) -> ZoneStatusResponse:
    now = datetime.now(timezone.utc)
    latest_prediction = PredictResponse(
        zone_id=zone_id,
        timestamp=now,
        stress_prob=0.62 if zone_id in {"A03", "F01"} else 0.38,
        uncertainty=0.16 if zone_id in {"A01", "E01"} else 0.29,
        confidence_flag=ConfidenceFlag.MEDIUM,
        degraded_mode=False,
        attention_weights=[0.4, 0.35, 0.25],
        model_version="status-aggregate-demo",
        explanation=[],
        latency_ms=42.0,
    )
    rain_3h = extract_rain_3h(weather)
    moisture = 21.0 if zone_id in {"A03", "F01"} else 34.0
    latest_decision = LiveDecisionClient().recommend(
        RecommendRequest(
            zone_id=zone_id,
            stress_prob=latest_prediction.stress_prob,
            uncertainty=latest_prediction.uncertainty,
            degraded_mode=latest_prediction.degraded_mode,
            soil_moisture=moisture,
            rain_forecast_3h=rain_3h,
            attention_weights=latest_prediction.attention_weights,
        )
    )
    latest_telemetry = {
        "soil_moisture": moisture,
        "air_temp": weather.current.temperature_2m if weather.current else None,
        "humidity": weather.current.relative_humidity_2m if weather.current else None,
        "rain_3h": rain_3h,
        "source": "zone_status_aggregate",
        "timestamp": now.isoformat(),
    }
    alerts = build_alerts(zone_id, latest_prediction.stress_prob, moisture, rain_3h, now)
    imagery = ImagerySummary(
        scene_id=f"stub-scene-{zone_id.lower()}",
        acquisition_time=now - timedelta(days=5),
        cloud_cover=12.5,
        rgb_url=None,
        ndvi_url=None,
        stale=False,
    )
    return ZoneStatusResponse(
        zone_id=zone_id,
        latest_prediction=latest_prediction,
        latest_decision=latest_decision,
        latest_telemetry=latest_telemetry,
        weather=weather.model_dump(mode="json"),
        imagery=imagery,
        alerts=alerts,
        command_state=CommandStatus.PENDING,
        updated_at=now,
    )


def build_alerts(zone_id: str, stress_prob: float, moisture: float, rain_3h: float, now: datetime) -> list[AlertSummary]:
    return [
        AlertSummary(
            alert_id=alert.alert_id,
            severity=alert.severity,
            source=alert.source,
            message=alert.message,
            acknowledged=alert.acknowledged,
            timestamp=alert.timestamp,
        )
        for alert in build_zone_alert_records(
            zone_id,
            now,
            stress_prob=stress_prob,
            moisture=moisture,
            rain_3h=rain_3h,
        )
    ]


def build_zone_alert_records(
    zone_id: str,
    now: datetime,
    *,
    stress_prob: float | None = None,
    moisture: float | None = None,
    rain_3h: float | None = None,
    repository: AlertRepository | None = None,
) -> list[AlertRecord]:
    derived_stress = stress_prob if stress_prob is not None else (0.62 if zone_id in {"A03", "F01"} else 0.38)
    derived_moisture = moisture if moisture is not None else (21.0 if zone_id in {"A03", "F01"} else 34.0)
    derived_rain = rain_3h if rain_3h is not None else 0.12
    return evaluate_alerts(
        AlertEvaluationInput(
            zone_id=zone_id,
            timestamp=now,
            stress_prob=derived_stress,
            soil_moisture=derived_moisture,
            rain_forecast_3h=derived_rain,
            imagery_acquisition_time=now - timedelta(days=5),
            sensor_last_seen=now - timedelta(minutes=30),
        ),
        repository or AlertRepository(),
    )


def extract_rain_3h(weather: ZoneWeatherResponse) -> float:
    if weather.hourly is None or not weather.hourly.precipitation_probability:
        return 0.0
    next_values = weather.hourly.precipitation_probability[:3]
    filtered = [value for value in next_values if value is not None]
    if not filtered:
        return 0.0
    return max(filtered) / 100


@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    try:
        if not is_allowed_ws_origin(websocket):
            await websocket.close(code=1008, reason="Origin not allowed")
            return
        payload = authenticate_websocket(websocket)
        websocket.state.auth_context = payload
        check_rate_limit("ws-handshake", payload.get("sub", "anonymous"))
        await websocket.accept()
        await websocket.send_json({"type": "connected", "message": "stub"})
        while True:
            check_rate_limit("ws-message", payload.get("sub", "anonymous"))
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "data": data})
    except AgTechError as exc:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1008, reason=exc.message)
    except WebSocketDisconnect:
        pass
