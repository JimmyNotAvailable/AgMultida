"""AlignedSample: single Python representation of data_contract.yaml.

Every field is validated at construction time via __post_init__.
Violations raise ValueError with field name, expected value, and actual value.
No silent coercion, no silent dtype casting, no silent label clamping.

Synced with: contracts/data_contract.yaml v1.0.0
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import torch

SAMPLE_ID_PATTERN = re.compile(r"^[A-Z]\d{2}_\d{8}_[A-Z0-9]+$")
ZONE_ID_PATTERN = re.compile(r"^[A-Z]\d{2}$")

EXPECTED_SHAPES: dict[str, tuple[int, ...]] = {
    "image": (4, 224, 224),
    "sensor_seq": (48, 8),
    "weather_ctx": (6,),
    "modality_mask": (3,),
}

SOURCE_TRACE_REQUIRED_KEYS = frozenset({
    "image_source",
    "sensor_sources",
    "weather_source",
    "label_formula",
    "alignment_method",
    "cloud_rate",
})


@dataclass
class AlignedSample:
    """A single aligned multimodal sample for training/validation.

    Construction validates all contract invariants. If any field
    violates the contract, ValueError is raised immediately with
    a descriptive message.
    """

    sample_id: str
    zone_id: str
    timestamp: datetime
    image: torch.Tensor
    sensor_seq: torch.Tensor
    weather_ctx: torch.Tensor
    modality_mask: torch.Tensor
    label: float
    source_trace: dict[str, Any]

    def __post_init__(self) -> None:
        self._validate_ids()
        self._validate_timestamp()
        self._validate_tensors()
        self._validate_modality_mask()
        self._validate_label()
        self._validate_source_trace()

    def _validate_ids(self) -> None:
        if not SAMPLE_ID_PATTERN.match(self.sample_id):
            raise ValueError(
                f"sample_id '{self.sample_id}' does not match "
                f"pattern {SAMPLE_ID_PATTERN.pattern}"
            )
        if not ZONE_ID_PATTERN.match(self.zone_id):
            raise ValueError(
                f"zone_id '{self.zone_id}' does not match "
                f"pattern {ZONE_ID_PATTERN.pattern}"
            )

    def _validate_timestamp(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware (UTC). "
                f"Got naive datetime: {self.timestamp}"
            )

    def _validate_tensors(self) -> None:
        for name, expected_shape in EXPECTED_SHAPES.items():
            tensor = getattr(self, name)
            if not isinstance(tensor, torch.Tensor):
                raise ValueError(
                    f"{name}: expected torch.Tensor, got {type(tensor).__name__}"
                )
            if tensor.dtype != torch.float32:
                raise ValueError(
                    f"{name}: expected dtype float32, got {tensor.dtype}"
                )
            if tuple(tensor.shape) != expected_shape:
                raise ValueError(
                    f"{name}: expected shape {expected_shape}, "
                    f"got {tuple(tensor.shape)}"
                )

    def _validate_modality_mask(self) -> None:
        unique_vals = set(self.modality_mask.tolist())
        if not unique_vals.issubset({0.0, 1.0}):
            raise ValueError(
                f"modality_mask values must be in {{0.0, 1.0}}, "
                f"got {unique_vals}"
            )
        if self.modality_mask.sum().item() < 1.0:
            raise ValueError(
                "modality_mask: at least one modality must be present "
                "(sum >= 1). All modalities are masked out."
            )

    def _validate_label(self) -> None:
        if not (0.0 <= self.label <= 1.0):
            raise ValueError(
                f"label must be in [0.0, 1.0], got {self.label}"
            )

    def _validate_source_trace(self) -> None:
        if not isinstance(self.source_trace, dict):
            raise ValueError(
                f"source_trace: expected dict, got {type(self.source_trace).__name__}"
            )
        missing = SOURCE_TRACE_REQUIRED_KEYS - set(self.source_trace.keys())
        if missing:
            raise ValueError(
                f"source_trace missing required keys: {sorted(missing)}"
            )

    def to_model_dict(self) -> dict[str, torch.Tensor]:
        """Return dict matching MultimodalStressNet.forward() signature."""
        return {
            "image": self.image,
            "sensor_seq": self.sensor_seq,
            "weather_ctx": self.weather_ctx,
            "modality_mask": self.modality_mask,
        }
