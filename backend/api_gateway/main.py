"""API Gateway: central REST + WebSocket entry point.

Architecture ref: backend/api-gateway -> backend/api_gateway (Python-safe).
All endpoints return schemas from backend.core.schemas.

Client wiring controlled by GATEWAY_MODE env var:
  - "stub" (default): hardcoded mock responses via StubAIClient/StubDecisionClient
  - "live": routes to ai-serving via HTTP, decision-engine in-process

Endpoints:
  POST /v1/predict    -> PredictResponse
  POST /v1/recommend  -> IrrigationDecision
  POST /v1/telemetry  -> TelemetryIngestResponse
  POST /v1/commands   -> IrrigationCommandResponse
  GET  /v1/zones/{zone_id}/status -> ZoneStatusResponse
  GET  /v1/healthz    -> HealthResponse  (k8s liveness)
  GET  /v1/readyz     -> readiness status (k8s readiness)
  WS   /ws/updates    -> push events
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from core.schemas import (
    CommandStatus,
    ConfidenceFlag,
    HealthResponse,
    IrrigationCommandRequest,
    IrrigationCommandResponse,
    IrrigationDecision,
    PredictRequest,
    PredictResponse,
    RecAction,
    RecommendRequest,
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    ZoneStatusResponse,
)
from core.errors import AgTechError, mask_internal_exception
from core.config import get_settings

from api_gateway.clients.ai_client import StubAIClient, LiveAIClient
from api_gateway.clients.decision_client import StubDecisionClient, LiveDecisionClient


# ---------------------------------------------------------------------------
# Lifespan: initialize/teardown service clients based on GATEWAY_MODE
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()

    if settings.GATEWAY_MODE == "live":
        from core.http_client import create_http_client
        http = create_http_client(
            base_url=settings.AI_SERVING_URL,
            timeout_ms=settings.AI_SERVING_TIMEOUT_MS,
        )
        application.state.ai_client = LiveAIClient(http)
        application.state.decision_client = LiveDecisionClient()
    else:
        application.state.ai_client = StubAIClient()
        application.state.decision_client = StubDecisionClient()

    application.state.gateway_mode = settings.GATEWAY_MODE
    yield

    if hasattr(application.state, "ai_client") and hasattr(
        application.state.ai_client, "close"
    ):
        await application.state.ai_client.close()


app = FastAPI(
    title="AgMultida API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.ai_client = StubAIClient()
app.state.decision_client = StubDecisionClient()
app.state.gateway_mode = "stub"


# ---------------------------------------------------------------------------
# Exception handler: AgTechError -> ErrorResponse (no stacktrace leak)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Health (k8s liveness probe -- always ok if process is alive)
# ---------------------------------------------------------------------------
@app.get("/v1/healthz", response_model=HealthResponse)
async def healthz():
    return HealthResponse()


# ---------------------------------------------------------------------------
# Readiness (k8s readiness probe -- checks dependency wiring status)
# ---------------------------------------------------------------------------
@app.get("/v1/readyz")
async def readyz(request: Request):
    mode = getattr(request.app.state, "gateway_mode", "unknown")
    settings = get_settings()

    ai_dep = {"status": "stub"} if mode == "stub" else {
        "status": "configured",
        "url": settings.AI_SERVING_URL,
    }
    decision_dep = {"status": "stub"} if mode == "stub" else {
        "status": "in_process",
    }

    return {
        "status": "ok",
        "mode": mode,
        "dependencies": {
            "ai_serving": ai_dep,
            "decision_engine": decision_dep,
        },
    }


# ---------------------------------------------------------------------------
# Predict -- wired to AIClient (stub or live based on GATEWAY_MODE)
# ---------------------------------------------------------------------------
@app.post("/v1/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, request: Request):
    return await request.app.state.ai_client.predict(req)


# ---------------------------------------------------------------------------
# Recommend -- wired to DecisionClient (stub or live based on GATEWAY_MODE)
# ---------------------------------------------------------------------------
@app.post("/v1/recommend", response_model=IrrigationDecision)
async def recommend(req: RecommendRequest, request: Request):
    return request.app.state.decision_client.recommend(req)


# ---------------------------------------------------------------------------
# Telemetry -- STUB: will delegate to ingestion-service in future batch
# ---------------------------------------------------------------------------
@app.post("/v1/telemetry", response_model=TelemetryIngestResponse)
async def ingest_telemetry(req: TelemetryIngestRequest):
    # STUB: will delegate to ingestion-service
    return TelemetryIngestResponse(
        accepted=True,
        sample_id=f"{req.zone_id}_{req.timestamp.strftime('%Y%m%d%H%M')}",
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Commands -- STUB: will push to Redis Stream + MQTT in future batch
# ---------------------------------------------------------------------------
@app.post("/v1/commands", response_model=IrrigationCommandResponse)
async def create_command(req: IrrigationCommandRequest):
    return IrrigationCommandResponse(
        command_id=f"cmd_{uuid4().hex[:8]}",
        zone_id=req.zone_id,
        status=CommandStatus.PENDING,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Zone Status -- STUB: will query TimescaleDB + Redis cache
# ---------------------------------------------------------------------------
@app.get("/v1/zones/{zone_id}/status", response_model=ZoneStatusResponse)
async def zone_status(zone_id: str):
    return ZoneStatusResponse(
        zone_id=zone_id,
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# WebSocket -- STUB: will subscribe to Redis Pub/Sub
# ---------------------------------------------------------------------------
@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "message": "stub"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        pass
