"""Ingestion Service: IoT telemetry ingest via REST (MQTT subscriber deferred).

Architecture ref: backend/ingestion-service -> backend/ingestion_service.
STUB: accepts telemetry, returns ack. DB persistence + MQTT in Batch 3+.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.schemas import TelemetryIngestRequest, TelemetryIngestResponse
from core.errors import AgTechError, ErrorCode, mask_internal_exception

app = FastAPI(title="AgMultida Ingestion Service", version="1.0.0")


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


@app.post("/internal/telemetry", response_model=TelemetryIngestResponse)
async def ingest(req: TelemetryIngestRequest):
    """Accept IoT telemetry payload.

    STUB: validates schema and returns ack.
    Batch 3+ will persist to TimescaleDB and trigger alignment worker.
    """
    if not any(
        v is not None
        for v in req.measurements.model_dump().values()
    ):
        raise AgTechError(
            error_code=ErrorCode.TELEMETRY_REJECTED,
            message="At least one measurement field required",
            status_code=422,
        )

    sample_id = f"{req.zone_id}_{req.timestamp.strftime('%Y%m%d%H%M')}_{req.device_id}"
    return TelemetryIngestResponse(
        accepted=True,
        sample_id=sample_id,
        timestamp=datetime.now(timezone.utc),
    )
