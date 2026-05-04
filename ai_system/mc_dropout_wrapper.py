"""AI-layer MC Dropout wrapper: composes ONNX inference with post-processing.

This is the AI system's wrapper that sits ON TOP of backend/ai_serving/onnx_wrapper.py.
Backend wrapper handles: ONNX session, timeout, raw MC passes.
This wrapper adds: calibration, EMA smoothing, degraded logic, XAI, audit.

Separation of concerns:
  backend/ai_serving/onnx_wrapper.py  -> infrastructure (ONNX Runtime, timeout)
  ai_system/mc_dropout_wrapper.py     -> intelligence (calibration, smoothing, decisions)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ai_system.calibration import StressCalibrator
from ai_system.post_processor import PostProcessor, PostProcessedResult

logger = logging.getLogger("agtech.mc_dropout")


@dataclass
class AIInferenceResult:
    """Complete AI inference output ready for decision engine."""
    zone_id: str
    stress_prob: float
    uncertainty: float
    confidence_flag: str
    degraded_mode: bool
    attention_weights: list[float]
    model_version: str
    latency_ms: float


class AIInferencePipeline:
    """End-to-end AI inference: ONNX -> post-process -> structured output.

    Args:
        onnx_wrapper: Backend OnnxInferenceWrapper instance.
        calibrator: Fitted or stub StressCalibrator.
        model_version: Version string for audit trail.
    """

    def __init__(
        self,
        onnx_wrapper,
        calibrator: StressCalibrator | None = None,
        model_version: str = "v1.0.0",
    ) -> None:
        self._onnx = onnx_wrapper
        self._post_processor = PostProcessor(calibrator)
        self._model_version = model_version

    def predict(
        self,
        zone_id: str,
        image: np.ndarray,
        sensor_seq: np.ndarray,
        weather_ctx: np.ndarray,
        modality_mask: np.ndarray,
    ) -> AIInferenceResult:
        """Run full AI inference pipeline.

        Args:
            zone_id: Zone identifier.
            image: [1, 4, 224, 224] float32.
            sensor_seq: [1, 48, 8] float32.
            weather_ctx: [1, 6] float32.
            modality_mask: [1, 3] float32.

        Returns:
            AIInferenceResult with calibrated, smoothed prediction.
        """
        # Step 1: ONNX inference (backend wrapper handles MC Dropout + timeout)
        onnx_result = self._onnx.predict(image, sensor_seq, weather_ctx, modality_mask)

        # Step 2: Post-process (calibrate + EMA + degraded flag)
        raw_prob = float(onnx_result.prob_mean[0, 0])
        raw_uncertainty = float(onnx_result.uncertainty[0, 0])

        processed = self._post_processor.process(
            zone_id=zone_id,
            raw_prob=raw_prob,
            uncertainty=raw_uncertainty,
            modality_mask=modality_mask[0],  # [3]
        )

        # Merge degraded flags from both layers
        degraded = processed.degraded_mode or onnx_result.degraded_mode

        return AIInferenceResult(
            zone_id=zone_id,
            stress_prob=processed.stress_prob,
            uncertainty=processed.uncertainty,
            confidence_flag=processed.confidence_flag,
            degraded_mode=degraded,
            attention_weights=onnx_result.attention_weights[0].tolist(),
            model_version=self._model_version,
            latency_ms=onnx_result.latency_ms,
        )
