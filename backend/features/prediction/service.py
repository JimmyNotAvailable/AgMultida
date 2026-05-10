from __future__ import annotations

import logging
from uuid import uuid4

from core.errors import AgTechError, ErrorCode
from core.schemas import PredictRequest, PredictResponse
from features.prediction.cache import PredictionCacheService
from features.prediction.policy import apply_prediction_policy, build_prediction_source

logger = logging.getLogger("agmultida.prediction")


class PredictionService:
    def __init__(self, cache: PredictionCacheService) -> None:
        self._cache = cache

    async def complete_prediction(self, req: PredictRequest, prediction: PredictResponse) -> PredictResponse:
        self._validate_response_identity(req, prediction)
        source = build_prediction_source(prediction)
        policy_prediction = apply_prediction_policy(
            prediction,
            latency_ms=prediction.latency_ms,
            source=source,
        )
        prediction_id = policy_prediction.prediction_id or f"pred_{uuid4().hex[:12]}"
        completed = policy_prediction.model_copy(update={"prediction_id": prediction_id})
        await self._cache.store_success(completed, build_prediction_source(completed))
        self._log_completed(req, completed, build_prediction_source(completed))
        return completed

    def _validate_response_identity(self, req: PredictRequest, prediction: PredictResponse) -> None:
        if prediction.zone_id != req.zone_id or prediction.timestamp != req.timestamp:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_FAILED,
                message="AI serving returned an invalid response",
                status_code=502,
                details={"service": "ai_serving", "reason": "response_mismatch"},
            )

    def _log_completed(self, req: PredictRequest, prediction: PredictResponse, source: str) -> None:
        logger.info(
            "prediction_completed",
            extra={
                "event": "prediction_completed",
                "zone_id": req.zone_id,
                "stress_prob": prediction.stress_prob,
                "uncertainty": prediction.uncertainty,
                "degraded_mode": prediction.degraded_mode,
                "latency_ms": prediction.latency_ms,
                "trace_id": str(prediction.trace_id),
                "source": source,
            },
        )
