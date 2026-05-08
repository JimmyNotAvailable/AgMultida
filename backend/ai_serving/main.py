"""AI Serving: ONNX Runtime inference endpoint with manifest-driven input assembly."""
from __future__ import annotations

import ast
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_system.calibration import StressCalibrator
from ai_system.mc_dropout_wrapper import AIInferencePipeline
from ai_system.audit import AuditLogger
from ai_system.xai_explainer import explain_attention
from ai_serving.onnx_wrapper import OnnxInferenceWrapper
from core.config import get_settings
from core.errors import AgTechError, ErrorCode, mask_internal_exception
from core.schemas import ConfidenceFlag, HealthResponse, PredictRequest, PredictResponse

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - environment-dependent
    ort = None

logger = logging.getLogger("agtech.ai_serving")


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (Path(__file__).resolve().parents[2] / path).resolve()


class ManifestSampleStore:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.root_dir = manifest_path.parent
        self._frame = self._load_manifest()

    def _load_manifest(self) -> pd.DataFrame:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        frame = pd.read_csv(self.manifest_path)
        if frame.empty:
            raise ValueError(f"Manifest has no rows: {self.manifest_path}")
        required = {
            "sample_id", "zone_id", "timestamp_utc", "image_path", "sensor_seq_path",
            "weather_ctx_path", "modality_mask", "source_status",
        }
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Manifest missing required columns {sorted(missing)}")
        frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
        return frame.sort_values("timestamp_utc").reset_index(drop=True)

    def find_latest_sample(self, zone_id: str, timestamp: datetime) -> dict[str, Any]:
        target_ts = pd.Timestamp(timestamp.astimezone(timezone.utc))
        subset = self._frame[
            (self._frame["zone_id"] == zone_id)
            & (self._frame["source_status"] == "PASS")
            & (self._frame["timestamp_utc"] <= target_ts)
        ]
        if subset.empty:
            available = self._frame[self._frame["zone_id"] == zone_id]["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()[-5:]
            raise AgTechError(
                error_code=ErrorCode.ZONE_NOT_FOUND,
                message=f"No prediction sample available for zone {zone_id} at or before requested timestamp.",
                details={"zone_id": zone_id, "available_samples_hint": available},
                status_code=404,
            )
        row = subset.iloc[-1].to_dict()
        row["timestamp_utc"] = subset.iloc[-1]["timestamp_utc"].to_pydatetime()
        return row

    def assemble_inputs(self, row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        image = self._load_tensor(row["image_path"], (4, 224, 224))
        sensor_seq = self._load_tensor(row["sensor_seq_path"], (48, 8))
        weather_ctx = self._load_tensor(row["weather_ctx_path"], (6,))
        mask = self._parse_mask(row["modality_mask"])
        return (
            np.expand_dims(image, axis=0),
            np.expand_dims(sensor_seq, axis=0),
            np.expand_dims(weather_ctx, axis=0),
            np.expand_dims(mask, axis=0),
        )

    def _load_tensor(self, path_value: str, expected_shape: tuple[int, ...]) -> np.ndarray:
        path = self._resolve_path(path_value)
        arr = np.load(path).astype(np.float32)
        if tuple(arr.shape) != expected_shape:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_FAILED,
                message=f"Tensor shape mismatch for {path.name}",
                details={"expected_shape": expected_shape, "actual_shape": tuple(arr.shape)},
                status_code=500,
            )
        return arr

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute() and path.exists():
            return path
        candidate = (self.root_dir / path).resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Tensor path not found: {path_value}")

    def _parse_mask(self, value: Any) -> np.ndarray:
        parsed = ast.literal_eval(str(value))
        mask = np.array(parsed, dtype=np.float32)
        if mask.shape != (3,):
            raise ValueError(f"Invalid modality_mask shape: {mask.shape}")
        return mask


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.audit_logger = AuditLogger()
    app.state.sample_store = None
    app.state.pipeline = None
    app.state.readiness_error = None

    try:
        manifest_path = _resolve_project_path(settings.MANIFEST_PATH)
        app.state.sample_store = ManifestSampleStore(manifest_path)

        if ort is None:
            raise RuntimeError("onnxruntime is not installed")
        model_path = _resolve_project_path(settings.ONNX_MODEL_PATH)
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        wrapper = OnnxInferenceWrapper(session, timeout_ms=settings.AI_SERVING_TIMEOUT_MS)

        calibrator = None
        calibrator_path = _resolve_project_path(settings.CALIBRATOR_PATH)
        if calibrator_path.exists():
            try:
                calibrator = StressCalibrator.load(calibrator_path)
            except Exception:  # pragma: no cover - fail-open by design
                logger.exception("Failed to load calibrator, continuing without it")
        app.state.pipeline = AIInferencePipeline(
            onnx_wrapper=wrapper,
            calibrator=calibrator,
            model_version=settings.MODEL_VERSION,
        )
        logger.info("AI serving ready with manifest=%s model=%s", manifest_path, model_path)
    except Exception as error:  # pragma: no cover - startup path
        logger.exception("AI serving startup degraded: %s", error)
        app.state.readiness_error = str(error)
        if settings.AI_SERVING_STRICT_READY:
            raise
    yield


app = FastAPI(title="AgMultida AI Serving", version="1.0.0", lifespan=lifespan)


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


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse()


@app.get("/readyz")
async def readyz(request: Request) -> dict[str, Any]:
    pipeline_ready = request.app.state.pipeline is not None
    manifest_ready = request.app.state.sample_store is not None
    ready = pipeline_ready and manifest_ready and request.app.state.readiness_error is None
    return {
        "status": "ok" if ready else "degraded",
        "model_loaded": pipeline_ready,
        "manifest_loaded": manifest_ready,
        "mode": request.app.state.settings.AI_SERVING_MODE,
        "readiness_error": request.app.state.readiness_error,
    }


@app.post("/internal/predict", response_model=PredictResponse)
async def internal_predict(
    req: PredictRequest,
    request: Request,
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
):
    settings = request.app.state.settings
    expected_key = settings.INTERNAL_API_KEY
    if expected_key and x_internal_api_key != expected_key:
        raise AgTechError(
            error_code=ErrorCode.AUTH_INVALID_API_KEY,
            message="Invalid internal API key.",
            status_code=401,
        )

    if request.app.state.pipeline is None or request.app.state.sample_store is None:
        raise AgTechError(
            error_code=ErrorCode.MODEL_NOT_FOUND,
            message="Inference pipeline is not ready.",
            details={"readiness_error": request.app.state.readiness_error},
            status_code=503,
        )

    row = request.app.state.sample_store.find_latest_sample(req.zone_id, req.timestamp)
    image, sensor_seq, weather_ctx, modality_mask = request.app.state.sample_store.assemble_inputs(row)
    result = request.app.state.pipeline.predict(
        zone_id=req.zone_id,
        image=image,
        sensor_seq=sensor_seq,
        weather_ctx=weather_ctx,
        modality_mask=modality_mask,
    )
    explanations = [item.__dict__ for item in explain_attention(result.attention_weights, sensor_seq[0], top_k=3)]
    request.app.state.audit_logger.log_prediction(
        trace_id=None,
        zone_id=req.zone_id,
        model_version=result.model_version,
        image=image,
        sensor_seq=sensor_seq,
        weather_ctx=weather_ctx,
        modality_mask=modality_mask,
        stress_prob=result.stress_prob,
        uncertainty=result.uncertainty,
        decision_action="predict_only",
        decision_reason="internal_predict",
        degraded_mode=result.degraded_mode,
        latency_ms=result.latency_ms,
        confidence_flag=result.confidence_flag,
    )
    return PredictResponse(
        zone_id=req.zone_id,
        timestamp=req.timestamp,
        stress_prob=result.stress_prob,
        uncertainty=min(1.0, max(0.0, result.uncertainty)),
        confidence_flag=ConfidenceFlag(result.confidence_flag),
        degraded_mode=result.degraded_mode,
        attention_weights=result.attention_weights,
        model_version=req.model_version or result.model_version,
        explanation=explanations,
        latency_ms=result.latency_ms,
    )
