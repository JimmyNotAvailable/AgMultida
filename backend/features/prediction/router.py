from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.schemas import PredictRequest, PredictResponse, TelemetryIngestRequest, TelemetryIngestResponse
from backend.features.websocket.publish import publish_realtime_event

router = APIRouter(tags=["prediction"])


@router.post("/v1/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, request: Request):
    prediction = await request.app.state.ai_client.predict(req)
    prediction = await request.app.state.prediction_service.complete_prediction(req, prediction)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    await publish_realtime_event(request.app, "prediction_completed", req.zone_id, {"zone_id": req.zone_id, "prediction_id": prediction.prediction_id})
    return prediction


@router.post("/v1/telemetry", response_model=TelemetryIngestResponse)
async def ingest_telemetry(req: TelemetryIngestRequest, request: Request):
    response = await request.app.state.ingestion_client.ingest(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    return response
