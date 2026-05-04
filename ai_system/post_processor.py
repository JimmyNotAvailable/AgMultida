"""Post-processor: calibrate, smooth, and flag degraded predictions.

Pipeline: raw_prob -> calibrate -> EMA smooth -> confidence flag -> output.
Each zone maintains its own EMA state for temporal smoothing.

Safety invariant: assert uncertainty >= 0.0 (Senior Review).
Missing modality always sets degraded_mode=true and uncertainty *= 1.3.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ai_system.calibration import StressCalibrator

logger = logging.getLogger("agtech.post_processor")

DEGRADED_UNCERTAINTY_MULTIPLIER = 1.3
EMA_ALPHA_NORMAL = 0.6
EMA_ALPHA_DEGRADED = 0.4


@dataclass
class PostProcessedResult:
    """Output of the post-processing pipeline."""
    zone_id: str
    stress_prob: float
    uncertainty: float
    confidence_flag: str  # high | medium | low
    degraded_mode: bool


class PostProcessor:
    """Calibrate, smooth, and assess confidence of stress predictions."""

    def __init__(self, calibrator: StressCalibrator | None = None) -> None:
        self._calibrator = calibrator or StressCalibrator()
        self._ema_state: dict[str, float] = defaultdict(lambda: 0.5)

    def process(
        self,
        zone_id: str,
        raw_prob: float,
        uncertainty: float,
        modality_mask: np.ndarray,
    ) -> PostProcessedResult:
        """Full post-processing pipeline.

        Args:
            zone_id: Zone identifier for EMA state tracking.
            raw_prob: Raw sigmoid probability from model.
            uncertainty: Variance from MC Dropout.
            modality_mask: [3] array, 1.0=present, 0.0=missing.
        """
        # JUN: Senior Review -- defensive assertion
        assert uncertainty >= 0.0, f"Uncertainty must be non-negative, got {uncertainty}"

        # Detect missing modality
        degraded = bool(np.any(modality_mask < 1.0))
        if degraded:
            uncertainty = uncertainty * DEGRADED_UNCERTAINTY_MULTIPLIER
            logger.info(
                "zone=%s degraded_mode=true missing_modalities=%s",
                zone_id,
                np.where(modality_mask < 1.0)[0].tolist(),
            )

        # Calibrate
        calibrated = self._calibrator.predict(np.array([raw_prob]))[0]

        # EMA smooth
        alpha = EMA_ALPHA_DEGRADED if degraded else EMA_ALPHA_NORMAL
        prev = self._ema_state[zone_id]
        smoothed = float(alpha * calibrated + (1.0 - alpha) * prev)
        self._ema_state[zone_id] = smoothed

        # Confidence flag
        if uncertainty > 0.30:
            flag = "low"
        elif uncertainty > 0.15:
            flag = "medium"
        else:
            flag = "high"

        return PostProcessedResult(
            zone_id=zone_id,
            stress_prob=smoothed,
            uncertainty=float(uncertainty),
            confidence_flag=flag,
            degraded_mode=degraded,
        )
