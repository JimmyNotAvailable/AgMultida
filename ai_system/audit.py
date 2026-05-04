"""Audit logger: structured prediction audit trail.

Guard #6 compliance: NEVER logs raw tensors, tokens, API keys, JWTs, or secrets.
Only logs: hashes, metadata, trace_id, model_version, latency, decision,
uncertainty, degraded_mode.

Input tensors are hashed via SHA-256 for deduplication and traceability
without storing the actual payload.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import numpy as np

logger = logging.getLogger("agtech.audit")


def _hash_tensor(arr: np.ndarray) -> str:
    """SHA-256 hash of tensor bytes for audit without storing raw data."""
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _hash_dict(d: dict) -> str:
    """SHA-256 hash of dict for audit."""
    raw = json.dumps(d, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class AuditEntry:
    """Single audit log entry for a prediction/decision cycle."""

    def __init__(
        self,
        trace_id: UUID | str,
        zone_id: str,
        model_version: str,
        input_hash: str,
        stress_prob: float,
        uncertainty: float,
        decision_action: str,
        decision_reason: str,
        degraded_mode: bool,
        latency_ms: float,
        require_ack: bool = False,
        confidence_flag: str = "high",
    ) -> None:
        self.trace_id = str(trace_id)
        self.zone_id = zone_id
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.model_version = model_version
        self.input_hash = input_hash
        self.stress_prob = round(stress_prob, 6)
        self.uncertainty = round(uncertainty, 6)
        self.decision_action = decision_action
        self.decision_reason = decision_reason
        self.degraded_mode = degraded_mode
        self.latency_ms = round(latency_ms, 2)
        self.require_ack = require_ack
        self.confidence_flag = confidence_flag

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "zone_id": self.zone_id,
            "timestamp": self.timestamp,
            "model_version": self.model_version,
            "input_hash": self.input_hash,
            "stress_prob": self.stress_prob,
            "uncertainty": self.uncertainty,
            "decision_action": self.decision_action,
            "decision_reason": self.decision_reason,
            "degraded_mode": self.degraded_mode,
            "latency_ms": self.latency_ms,
            "require_ack": self.require_ack,
            "confidence_flag": self.confidence_flag,
        }


class AuditLogger:
    """Structured audit logger for prediction/decision cycles.

    Logs to structured JSON logger. In production, a DB writer
    (TimescaleDB audit_predictions hypertable) will consume these entries.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def log_prediction(
        self,
        trace_id: UUID | str | None,
        zone_id: str,
        model_version: str,
        image: np.ndarray,
        sensor_seq: np.ndarray,
        weather_ctx: np.ndarray,
        modality_mask: np.ndarray,
        stress_prob: float,
        uncertainty: float,
        decision_action: str,
        decision_reason: str,
        degraded_mode: bool,
        latency_ms: float,
        require_ack: bool = False,
        confidence_flag: str = "high",
    ) -> AuditEntry:
        """Create and log an audit entry.

        Raw tensors are hashed -- never stored or logged directly.
        """
        input_hash = _hash_dict({
            "image": _hash_tensor(image),
            "sensor_seq": _hash_tensor(sensor_seq),
            "weather_ctx": _hash_tensor(weather_ctx),
            "modality_mask": _hash_tensor(modality_mask),
        })

        entry = AuditEntry(
            trace_id=trace_id or uuid4(),
            zone_id=zone_id,
            model_version=model_version,
            input_hash=input_hash,
            stress_prob=stress_prob,
            uncertainty=uncertainty,
            decision_action=decision_action,
            decision_reason=decision_reason,
            degraded_mode=degraded_mode,
            latency_ms=latency_ms,
            require_ack=require_ack,
            confidence_flag=confidence_flag,
        )

        self._entries.append(entry)
        logger.info("audit_prediction %s", json.dumps(entry.to_dict()))
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)
