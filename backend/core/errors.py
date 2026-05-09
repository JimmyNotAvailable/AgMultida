"""AgTech error contract: structured error responses with trace_id injection.

Design rationale: Error codes are domain-specific enums, not HTTP status codes.
Internal exceptions are caught and masked -- stacktraces never leak to clients.
Synced with: contracts/openapi.yaml error schema.
"""
from __future__ import annotations

import enum
import logging
import traceback
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("agtech.errors")


class ErrorCode(str, enum.Enum):
    """Domain-specific error codes for the AgTech API."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    ZONE_NOT_FOUND = "ZONE_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    VALVE_ACK_TIMEOUT = "VALVE_ACK_TIMEOUT"
    COMMAND_FAILED = "COMMAND_FAILED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_INSUFFICIENT_ROLE = "AUTH_INSUFFICIENT_ROLE"
    AUTH_INVALID_API_KEY = "AUTH_INVALID_API_KEY"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TELEMETRY_REJECTED = "TELEMETRY_REJECTED"
    DEGRADED_SERVICE = "DEGRADED_SERVICE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    """Standardized error response. Never contains internal stacktrace."""
    error_code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgTechError(Exception):
    """Base exception for all AgTech domain errors.

    Catches and converts to ErrorResponse at the FastAPI exception handler
    boundary, ensuring no internal details leak to the client.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
        trace_id: Optional[UUID] = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        self.trace_id = trace_id or uuid4()
        super().__init__(message)

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            trace_id=self.trace_id,
        )


def mask_internal_exception(exc: Exception, trace_id: Optional[UUID] = None) -> ErrorResponse:
    """Convert unexpected exceptions to safe ErrorResponse.

    Logs the full traceback server-side but returns only a generic
    message to the client, preventing stacktrace leakage.
    """
    tid = trace_id or uuid4()
    logger.error(
        "Unhandled exception [trace_id=%s]: %s\n%s",
        tid,
        exc,
        traceback.format_exc(),
    )
    return ErrorResponse(
        error_code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred. Contact support with trace_id.",
        details={"trace_id": str(tid)},
        trace_id=tid,
    )
