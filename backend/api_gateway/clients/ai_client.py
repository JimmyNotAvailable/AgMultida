"""AI Serving client abstraction with stub/live modes.

Protocol-based design: any object with a matching ``predict`` method
satisfies the AIClient contract. No ABC inheritance required.

StubAIClient: returns hardcoded mock predictions (current Batch 2 behavior).
LiveAIClient: calls ai-serving ``/internal/predict`` via httpx.AsyncClient,
    translating transport exceptions into domain-specific AgTechErrors
    so the API boundary error contract is never violated.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
from pydantic import ValidationError

from features.prediction.policy import PREDICTION_MODALITY_UNCERTAINTY_PENALTY, PREDICTION_TIMEOUT_DEGRADE_MS

from core.schemas import (
    ConfidenceFlag,
    PredictRequest,
    PredictResponse,
)
from core.errors import AgTechError, ErrorCode


@runtime_checkable
class AIClient(Protocol):
    """Structural contract for AI serving communication."""

    async def predict(self, req: PredictRequest) -> PredictResponse: ...

    async def ready(self) -> dict[str, object]: ...


class StubAIClient:
    """Returns hardcoded mock predictions for testing and stub mode.

    Values are identical to the original Batch 2 inline stubs in
    api_gateway/main.py to ensure backward compatibility.
    """

    async def predict(self, req: PredictRequest) -> PredictResponse:
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

    async def ready(self) -> dict[str, object]:
        return {"status": "stub"}


class LiveAIClient:
    """Calls ai-serving /internal/predict via async HTTP.

    Translates httpx exceptions into AgTechErrors to maintain the
    error contract at the API boundary. Specific failure modes:
    - TimeoutException -> INFERENCE_TIMEOUT (504)
    - HTTPStatusError  -> INFERENCE_FAILED  (502)
    - HTTPError        -> INFERENCE_FAILED  (502)
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        internal_api_key: str = "",
        header_name: str = "X-Internal-API-Key",
    ) -> None:
        self._client = http_client
        self._internal_headers = (
            {header_name: internal_api_key}
            if internal_api_key
            else {}
        )

    async def predict(self, req: PredictRequest) -> PredictResponse:
        try:
            resp = await self._client.post(
                "/internal/predict",
                json=req.model_dump(mode="json"),
                headers=self._internal_headers or None,
            )
            resp.raise_for_status()
            prediction = PredictResponse.model_validate(resp.json())
            return self._apply_transport_policy(prediction)
        except (ValueError, ValidationError) as exc:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_FAILED,
                message="AI serving returned an invalid response",
                status_code=502,
                details={"service": "ai_serving", "reason": "invalid_response"},
            ) from exc
        except httpx.TimeoutException as exc:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_TIMEOUT,
                message="AI serving did not respond within timeout",
                status_code=504,
                details={"service": "ai_serving"},
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_FAILED,
                message="AI serving returned an error",
                status_code=502,
                details={"upstream_status": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise AgTechError(
                error_code=ErrorCode.INFERENCE_FAILED,
                message="AI serving communication failure",
                status_code=502,
                details={"service": "ai_serving"},
            ) from exc

    def _apply_transport_policy(self, prediction: PredictResponse) -> PredictResponse:
        degraded = prediction.degraded_mode or prediction.latency_ms > PREDICTION_TIMEOUT_DEGRADE_MS
        uncertainty = prediction.uncertainty
        if len(prediction.attention_weights) < 3:
            uncertainty = min(1.0, uncertainty + PREDICTION_MODALITY_UNCERTAINTY_PENALTY)
        return prediction.model_copy(
            update={
                "degraded_mode": degraded,
                "confidence_flag": ConfidenceFlag.LOW if degraded else prediction.confidence_flag,
                "uncertainty": uncertainty,
            }
        )

    async def ready(self) -> dict[str, object]:
        try:
            resp = await self._client.get(
                "/readyz",
                headers=self._internal_headers or None,
            )
            resp.raise_for_status()
            body = resp.json()
            return {
                "status": body.get("status", "degraded"),
                "model_loaded": body.get("model_loaded"),
                "manifest_loaded": body.get("manifest_loaded"),
                "upstream_last_error": body.get("readiness_error"),
            }
        except httpx.TimeoutException:
            return {
                "status": "degraded",
                "model_loaded": None,
                "manifest_loaded": None,
                "upstream_last_error": "AI serving readiness probe timed out",
            }
        except httpx.HTTPError:
            return {
                "status": "degraded",
                "model_loaded": None,
                "manifest_loaded": None,
                "upstream_last_error": "AI serving readiness probe failed",
            }

    async def close(self) -> None:
        """Shutdown hook: release connection pool."""
        await self._client.aclose()
