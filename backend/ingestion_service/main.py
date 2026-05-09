"""Ingestion Service: IoT telemetry ingest via REST (MQTT subscriber deferred)."""
from __future__ import annotations

import hmac
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.db import check_database_ready, close_db_pool, ensure_device_registered, execute, fetch_one, open_db_pool
from core.errors import AgTechError, ErrorCode, mask_internal_exception
from core.schemas import HealthResponse, TelemetryIngestRequest, TelemetryIngestResponse


@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        await open_db_pool()
    except RuntimeError:
        application.state.db_enabled = False
    else:
        application.state.db_enabled = True
    yield
    await close_db_pool()


app = FastAPI(title="AgMultida Ingestion Service", version="1.0.0", lifespan=lifespan)
app.state.db_enabled = False


def require_internal_api_key(request: Request) -> None:
    settings = get_settings()
    expected_key = settings.INTERNAL_API_KEY
    header_name = settings.INTERNAL_API_KEY_HEADER
    provided_key = request.headers.get(header_name)
    if not provided_key or not expected_key or not hmac.compare_digest(provided_key, expected_key):
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_API_KEY,
            message='Invalid internal API key.',
            details={'source_service': 'api_gateway'},
            status_code=401,
            trace_id=uuid4(),
        )


def build_sample_id(req: TelemetryIngestRequest) -> str:
    return f"{req.zone_id}_{req.timestamp.strftime('%Y%m%d%H%M')}_{req.device_id}"


async def ensure_zone_exists(zone_id: str) -> None:
    zone = await fetch_one('SELECT zone_id FROM zones WHERE zone_id = %s', (zone_id,))
    if zone is None:
        raise AgTechError(
            error_code=ErrorCode.ZONE_NOT_FOUND,
            message=f'Zone {zone_id} not found',
            status_code=404,
        )


async def persist_telemetry(req: TelemetryIngestRequest, sample_id: str) -> None:
    await ensure_zone_exists(req.zone_id)
    await ensure_device_registered(req.device_id, req.zone_id)
    await execute(
        '''
        INSERT INTO sensor_telemetry (
            time,
            sample_id,
            device_id,
            zone_id,
            soil_moisture,
            soil_temp,
            air_temp,
            humidity,
            ec,
            ph,
            rain_3h,
            rain_24h
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (
            req.timestamp,
            sample_id,
            req.device_id,
            req.zone_id,
            req.measurements.soil_moisture,
            req.measurements.soil_temp,
            req.measurements.air_temp,
            req.measurements.humidity,
            req.measurements.ec,
            req.measurements.ph,
            req.measurements.rain_3h,
            req.measurements.rain_24h,
        ),
    )


@app.exception_handler(AgTechError)
async def agtech_error_handler(request: Request, exc: AgTechError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response().model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    resp = mask_internal_exception(exc)
    return JSONResponse(status_code=500, content=resp.model_dump(mode="json"))


@app.get('/healthz', response_model=HealthResponse)
async def healthz():
    return HealthResponse()


@app.get('/readyz')
async def readyz(request: Request):
    if request.app.state.db_enabled:
        database = await check_database_ready()
    else:
        database = {'status': 'disabled'}
    return {
        'status': 'ok' if database['status'] == 'ok' else 'degraded',
        'dependencies': {'database': database},
    }


@app.post("/internal/telemetry", response_model=TelemetryIngestResponse)
async def ingest(req: TelemetryIngestRequest, request: Request):
    require_internal_api_key(request)
    if not any(v is not None for v in req.measurements.model_dump().values()):
        raise AgTechError(
            error_code=ErrorCode.TELEMETRY_REJECTED,
            message="At least one measurement field required",
            status_code=422,
        )
    if not request.app.state.db_enabled:
        raise AgTechError(
            error_code=ErrorCode.DEGRADED_SERVICE,
            message='Database not configured for ingestion service',
            status_code=503,
        )

    sample_id = build_sample_id(req)
    await persist_telemetry(req, sample_id)
    return TelemetryIngestResponse(
        accepted=True,
        sample_id=sample_id,
        timestamp=datetime.now(timezone.utc),
    )
