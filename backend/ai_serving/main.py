"""AI Serving: ONNX Runtime inference endpoint.

Architecture ref: backend/ai-serving -> backend/ai_serving (Python-safe).
Uses OnnxInferenceWrapper from onnx_wrapper.py (Batch 1).
Stub mode returns mock predictions until ONNX model is trained.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.schemas import ConfidenceFlag, PredictRequest, PredictResponse
from core.errors import AgTechError, mask_internal_exception

app = FastAPI(title="AgMultida AI Serving", version="1.0.0")


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


@app.post("/internal/predict", response_model=PredictResponse)
async def internal_predict(req: PredictRequest):
    """Internal endpoint called by api-gateway. Not exposed to clients.

    STUB: returns mock prediction. Will load ONNX model and run
    OnnxInferenceWrapper.predict() after GATE_3_ML_SMOKE passes.
    """
    # STUB: mock inference result
    return PredictResponse(
        zone_id=req.zone_id,
        timestamp=req.timestamp,
        stress_prob=0.35,
        uncertainty=0.12,
        confidence_flag=ConfidenceFlag.HIGH,
        degraded_mode=False,
        attention_weights=[0.3, 0.25, 0.15, 0.1, 0.08, 0.07, 0.05],
        model_version=req.model_version or "v1.0.0-stub",
        latency_ms=42.0,
    )
