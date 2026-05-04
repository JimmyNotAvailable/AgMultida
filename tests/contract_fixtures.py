"""Contract fixture tests: validate Pydantic schemas against mock data.

Ensures BE and ML consume the same contract.
Run: pytest tests/contract_fixtures.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.core.errors import AgTechError, ErrorCode, ErrorResponse, mask_internal_exception
from backend.core.schemas import (
    CommandStatus,
    ConfidenceFlag,
    FeatureImportance,
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
    TelemetryMeasurement,
    ZoneStatusResponse,
)

# ---------------------------------------------------------------------------
# Fixture data aligned with contracts/data_contract.yaml
# ---------------------------------------------------------------------------
VALID_PREDICT_REQUEST = {
    "zone_id": "A01",
    "timestamp": "2024-02-14T03:21:00Z",
}

VALID_PREDICT_RESPONSE = {
    "trace_id": str(uuid4()),
    "zone_id": "A01",
    "timestamp": "2024-02-14T03:21:00Z",
    "stress_prob": 0.42,
    "uncertainty": 0.18,
    "confidence_flag": "high",
    "degraded_mode": False,
    "attention_weights": [0.3, 0.25, 0.15, 0.1, 0.08, 0.07, 0.05],
    "model_version": "v1.0.0",
    "explanation": [
        {"feature": "soil_moisture_24h", "weight": 0.42, "trend": "decreasing"},
        {"feature": "ndvi_drop", "weight": 0.31, "trend": "stable"},
    ],
    "latency_ms": 123.4,
}

VALID_RECOMMEND_REQUEST = {
    "zone_id": "A01",
    "stress_prob": 0.65,
    "uncertainty": 0.12,
    "degraded_mode": False,
    "soil_moisture": 22.0,
    "rain_forecast_3h": 0.1,
    "attention_weights": [0.3, 0.25, 0.15],
}

VALID_TELEMETRY_REQUEST = {
    "device_id": "iot_sensor_001",
    "zone_id": "A01",
    "timestamp": "2024-02-14T03:00:00Z",
    "measurements": {
        "soil_moisture": 28.5,
        "soil_temp": 29.4,
        "air_temp": 34.2,
        "humidity": 61.0,
        "rain_3h": 0.0,
    },
}

VALID_COMMAND_REQUEST = {
    "zone_id": "A01",
    "action": "moderate",
    "volume_mm": 12.0,
    "source": "ai_recommendation",
}


# ---------------------------------------------------------------------------
# PredictRequest / PredictResponse
# ---------------------------------------------------------------------------
class TestPredictContract:
    def test_valid_request(self):
        req = PredictRequest(**VALID_PREDICT_REQUEST)
        assert req.zone_id == "A01"
        assert req.timestamp.tzinfo is not None or req.timestamp is not None

    def test_invalid_zone_id_rejected(self):
        with pytest.raises(Exception):
            PredictRequest(zone_id="invalid", timestamp="2024-02-14T03:21:00Z")

    def test_extra_fields_rejected(self):
        """ConfigDict(extra='forbid') blocks mass assignment."""
        with pytest.raises(Exception):
            PredictRequest(zone_id="A01", timestamp="2024-02-14T03:21:00Z", hacked="yes")

    def test_valid_response(self):
        resp = PredictResponse(**VALID_PREDICT_RESPONSE)
        assert 0.0 <= resp.stress_prob <= 1.0
        assert 0.0 <= resp.uncertainty <= 1.0
        assert resp.trace_id is not None
        assert resp.degraded_mode is False

    def test_response_has_trace_id(self):
        """Senior Review: trace_id UUID4 on every response."""
        resp = PredictResponse(**VALID_PREDICT_RESPONSE)
        assert resp.trace_id is not None

    def test_stress_prob_out_of_range_rejected(self):
        data = {**VALID_PREDICT_RESPONSE, "stress_prob": 1.5}
        with pytest.raises(Exception):
            PredictResponse(**data)


# ---------------------------------------------------------------------------
# RecommendRequest / IrrigationDecision
# ---------------------------------------------------------------------------
class TestRecommendContract:
    def test_valid_request(self):
        req = RecommendRequest(**VALID_RECOMMEND_REQUEST)
        assert req.stress_prob == 0.65

    def test_irrigation_decision_all_actions(self):
        for action in RecAction:
            dec = IrrigationDecision(
                action=action,
                volume_mm=5.0,
                require_ack=(action == RecAction.HOLD),
                reason="test",
            )
            assert dec.trace_id is not None
            assert dec.action == action


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
class TestTelemetryContract:
    def test_valid_ingest(self):
        req = TelemetryIngestRequest(**VALID_TELEMETRY_REQUEST)
        assert req.measurements.soil_moisture == 28.5

    def test_partial_measurements_ok(self):
        """Sensors may report partial data."""
        req = TelemetryIngestRequest(
            device_id="d1",
            zone_id="B07",
            timestamp="2024-02-14T03:00:00Z",
            measurements={"soil_moisture": 30.0},
        )
        assert req.measurements.air_temp is None


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------
class TestCommandContract:
    def test_valid_command(self):
        req = IrrigationCommandRequest(**VALID_COMMAND_REQUEST)
        assert req.action == RecAction.MODERATE

    def test_command_response_has_trace_id(self):
        resp = IrrigationCommandResponse(
            command_id="cmd_001",
            zone_id="A01",
            status=CommandStatus.PENDING,
            timestamp=datetime.now(timezone.utc),
        )
        assert resp.trace_id is not None


# ---------------------------------------------------------------------------
# Error Contract
# ---------------------------------------------------------------------------
class TestErrorContract:
    def test_error_response_no_stacktrace(self):
        resp = ErrorResponse(
            error_code=ErrorCode.INFERENCE_TIMEOUT,
            message="Inference timed out after 500ms",
            details={"zone_id": "C19"},
        )
        serialized = resp.model_dump_json()
        assert "Traceback" not in serialized
        assert resp.trace_id is not None

    def test_agtech_error_to_response(self):
        err = AgTechError(
            error_code=ErrorCode.ZONE_NOT_FOUND,
            message="Zone X99 not found",
            status_code=404,
        )
        resp = err.to_response()
        assert resp.error_code == ErrorCode.ZONE_NOT_FOUND
        assert resp.trace_id is not None

    def test_mask_internal_exception(self):
        """Internal exceptions must not leak details to client."""
        try:
            raise ValueError("secret database connection string here")
        except ValueError as exc:
            resp = mask_internal_exception(exc)
            assert "secret" not in resp.message
            assert "database" not in resp.message
            assert resp.error_code == ErrorCode.INTERNAL_ERROR


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class TestHealthContract:
    def test_health_response(self):
        resp = HealthResponse()
        assert resp.status == "ok"
