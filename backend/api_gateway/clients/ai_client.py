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


class LiveAIClient:
    """Calls ai-serving /internal/predict via async HTTP.

    Translates httpx exceptions into AgTechErrors to maintain the
    error contract at the API boundary. Specific failure modes:
    - TimeoutException -> INFERENCE_TIMEOUT (504)
    - HTTPStatusError  -> INFERENCE_FAILED  (502)
    - HTTPError        -> INFERENCE_FAILED  (502)
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def predict(self, req: PredictRequest) -> PredictResponse:
        try:
            resp = await self._client.post(
                "/internal/predict",
                content=req.model_dump_json(),
            )
            resp.raise_for_status()
            return PredictResponse.model_validate(resp.json())
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

    async def close(self) -> None:
        """Shutdown hook: release connection pool."""
        await self._client.aclose()
