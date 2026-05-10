from __future__ import annotations

from dataclasses import dataclass

from core.schemas import ConfidenceFlag, PredictResponse

PREDICTION_LATEST_TTL_SECONDS = 600
PREDICTION_BUCKET_TTL_SECONDS = 1800
PREDICTION_MEMORY_TTL_SECONDS = 600
PREDICTION_TIMEOUT_DEGRADE_MS = 500
PREDICTION_MODALITY_UNCERTAINTY_PENALTY = 0.15


@dataclass(frozen=True)
class PredictionMetadata:
    source: str
    created_at: str
    trace_id: str
    model_version: str


def apply_prediction_policy(
    prediction: PredictResponse,
    *,
    latency_ms: float,
    source: str,
    missing_modality_count: int = 0,
) -> PredictResponse:
    degraded = prediction.degraded_mode or latency_ms > PREDICTION_TIMEOUT_DEGRADE_MS
    uncertainty = min(1.0, prediction.uncertainty + (PREDICTION_MODALITY_UNCERTAINTY_PENALTY if missing_modality_count > 0 else 0.0))
    confidence_flag = ConfidenceFlag.LOW if degraded else _confidence_from_uncertainty(uncertainty)
    return prediction.model_copy(
        update={
            "degraded_mode": degraded,
            "uncertainty": uncertainty,
            "confidence_flag": confidence_flag,
        }
    )


def build_prediction_source(prediction: PredictResponse) -> str:
    trace_id = str(prediction.trace_id)
    if "demo-" in trace_id:
        return "demo"
    if prediction.degraded_mode:
        return "degraded"
    return "live"


def prediction_timestamp_bucket(timestamp: str) -> str:
    return timestamp[:16].replace(":", "-")


def _confidence_from_uncertainty(uncertainty: float) -> ConfidenceFlag:
    if uncertainty < 0.15:
        return ConfidenceFlag.HIGH
    if uncertainty <= 0.30:
        return ConfidenceFlag.MEDIUM
    return ConfidenceFlag.LOW
