"""Pydantic schemas for MultimodalAgTech API contracts.

All response models include trace_id (UUID4) for end-to-end audit trail.
Single source of truth shared between BE endpoints and AI system output validation.
Synced with: contracts/data_contract.yaml, contracts/decision_contract.yaml
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RecAction(str, enum.Enum):
    """Irrigation recommendation actions mapped from decision_contract.yaml."""
    NO_IRRIGATION = "no_irrigation"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    HOLD = "hold"


class ConfidenceFlag(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CommandStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    OVERRIDDEN = "OVERRIDDEN"


class FeatureImportance(BaseModel):
    """XAI payload element: attention-derived feature contribution."""
    feature: str
    weight: float = Field(ge=0.0, le=1.0)
    trend: str  # increasing | decreasing | stable | unknown


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    """Request for stress prediction on a specific zone and timestamp."""
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    timestamp: datetime
    model_version: Optional[str] = None


class PredictResponse(BaseModel):
    """Stress prediction result with uncertainty and XAI payload."""
    trace_id: UUID = Field(default_factory=uuid4)
    zone_id: str
    timestamp: datetime
    stress_prob: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    confidence_flag: ConfidenceFlag
    degraded_mode: bool
    attention_weights: list[float]
    model_version: str
    explanation: list[FeatureImportance] = Field(default_factory=list)
    latency_ms: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------
class RecommendRequest(BaseModel):
    """Request for irrigation recommendation based on prediction context."""
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    stress_prob: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    degraded_mode: bool = False
    soil_moisture: float = Field(ge=0.0, le=100.0)
    rain_forecast_3h: float = Field(ge=0.0, le=1.0)
    attention_weights: list[float] = Field(default_factory=list)


class IrrigationDecision(BaseModel):
    """Irrigation decision output from the hybrid rule engine."""
    trace_id: UUID = Field(default_factory=uuid4)
    action: RecAction
    volume_mm: float = Field(ge=0.0, le=30.0)
    require_ack: bool
    reason: str
    safety_override: bool = False
    degraded_mode: bool = False
    confidence_flag: ConfidenceFlag = ConfidenceFlag.HIGH
    explanation: list[FeatureImportance] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
class TelemetryMeasurement(BaseModel):
    """Sensor readings from IoT device."""
    soil_moisture: Optional[float] = None
    soil_temp: Optional[float] = None
    air_temp: Optional[float] = None
    humidity: Optional[float] = None
    ec: Optional[float] = None
    ph: Optional[float] = None
    rain_3h: Optional[float] = None
    rain_24h: Optional[float] = None


class TelemetryIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    timestamp: datetime
    measurements: TelemetryMeasurement


class TelemetryIngestResponse(BaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    accepted: bool
    sample_id: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------
class IrrigationCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    action: RecAction
    volume_mm: float = Field(ge=0.0, le=30.0)
    source: str  # ai_recommendation | manual_override
    operator_note: Optional[str] = None


class IrrigationCommandResponse(BaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    command_id: str
    zone_id: str
    status: CommandStatus
    timestamp: datetime


# ---------------------------------------------------------------------------
# Zone Status
# ---------------------------------------------------------------------------
class ZoneStatusResponse(BaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    zone_id: str
    latest_prediction: Optional[PredictResponse] = None
    latest_decision: Optional[IrrigationDecision] = None
    latest_telemetry: Optional[TelemetryIngestResponse] = None
    command_state: Optional[CommandStatus] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    """Liveness/readiness probe for k8s. Added per Senior Review."""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
