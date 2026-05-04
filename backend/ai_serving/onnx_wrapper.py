"""ONNX Runtime inference wrapper with MC Dropout and timeout.

Design rationale:
- MC Dropout runs N forward passes with dropout ON to estimate uncertainty.
- Timeout fallback degrades to single-pass with explicit degraded_mode flag,
  satisfying the safety invariant: no silent fallback.
- Synced with: contracts/onnx_io_contract.yaml

Trade-off: MC Dropout (10 passes) increases latency ~10x vs single-pass.
The timeout mechanism (default 500ms) ensures we never block the API thread
beyond the SLA. If timeout triggers, we return single-pass result with
degraded_mode=true and inflated uncertainty (x1.3 per decision_contract).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger("agtech.onnx_wrapper")

# JUN: Default values synced with contracts/onnx_io_contract.yaml
DEFAULT_MC_PASSES = 10
DEFAULT_TIMEOUT_MS = 500
DEGRADED_UNCERTAINTY_MULTIPLIER = 1.3


@dataclass(frozen=True)
class InferenceResult:
    """Immutable inference output matching ONNX I/O contract."""
    logits_mean: np.ndarray  # [B, 1]
    prob_mean: np.ndarray    # [B, 1] -- sigmoid applied
    uncertainty: np.ndarray  # [B, 1] -- variance of sigmoid outputs
    attention_weights: np.ndarray  # [B, N]
    degraded_mode: bool
    passes_completed: int
    latency_ms: float


class OnnxInferenceWrapper:
    """MC Dropout inference wrapper over ONNX Runtime session.

    Args:
        session: Pre-loaded onnxruntime.InferenceSession.
        mc_passes: Number of MC Dropout forward passes.
        timeout_ms: Hard timeout for the full MC loop. On timeout,
            returns single-pass result with degraded_mode=true.
    """

    def __init__(
        self,
        session,  # ort.InferenceSession -- not type-hinted to avoid hard dep in tests
        mc_passes: int = DEFAULT_MC_PASSES,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._session = session
        self._mc_passes = mc_passes
        self._timeout_s = timeout_ms / 1000.0
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._input_names = [inp.name for inp in session.get_inputs()]
        self._output_names = [out.name for out in session.get_outputs()]

    def predict(
        self,
        image: np.ndarray,
        sensor_seq: np.ndarray,
        weather_ctx: np.ndarray,
        modality_mask: np.ndarray,
    ) -> InferenceResult:
        """Run MC Dropout inference with timeout fallback.

        Args:
            image: float32 [B, 4, 224, 224]
            sensor_seq: float32 [B, 48, 8]
            weather_ctx: float32 [B, 6]
            modality_mask: float32 [B, 3]

        Returns:
            InferenceResult with mean probability, uncertainty, and
            degraded_mode flag if timeout or single-pass fallback.
        """
        # JUN: Defensive assertions per Senior Review
        assert image.dtype == np.float32, f"image dtype must be float32, got {image.dtype}"
        assert sensor_seq.dtype == np.float32
        assert weather_ctx.dtype == np.float32
        assert modality_mask.dtype == np.float32

        feed = {
            "image": image,
            "sensor_seq": sensor_seq,
            "weather_ctx": weather_ctx,
            "modality_mask": modality_mask,
        }

        t0 = time.perf_counter()

        try:
            future = self._executor.submit(self._mc_loop, feed)
            all_logits, all_attn, passes = future.result(timeout=self._timeout_s)
            degraded = False
        except FuturesTimeout:
            logger.warning(
                "MC Dropout timed out after %.0fms, falling back to single-pass",
                self._timeout_s * 1000,
            )
            all_logits, all_attn = self._single_pass(feed)
            passes = 1
            degraded = True
        except Exception:
            logger.exception("ONNX inference failed, attempting single-pass fallback")
            all_logits, all_attn = self._single_pass(feed)
            passes = 1
            degraded = True

        latency_ms = (time.perf_counter() - t0) * 1000

        prob_all = _sigmoid(np.array(all_logits))  # [N, B, 1]
        prob_mean = prob_all.mean(axis=0)           # [B, 1]
        uncertainty = prob_all.var(axis=0)           # [B, 1]

        # JUN: Senior Review -- assert uncertainty is non-negative
        assert np.all(uncertainty >= 0.0), "Uncertainty must be non-negative"

        if degraded:
            uncertainty = uncertainty * DEGRADED_UNCERTAINTY_MULTIPLIER

        attn_mean = np.array(all_attn).mean(axis=0)  # [B, N]

        return InferenceResult(
            logits_mean=np.array(all_logits).mean(axis=0),
            prob_mean=prob_mean,
            uncertainty=uncertainty,
            attention_weights=attn_mean,
            degraded_mode=degraded,
            passes_completed=passes,
            latency_ms=latency_ms,
        )

    def _mc_loop(self, feed: dict) -> tuple:
        """Execute N forward passes for MC Dropout."""
        all_logits = []
        all_attn = []
        for _ in range(self._mc_passes):
            outputs = self._session.run(self._output_names, feed)
            all_logits.append(outputs[0])  # logits [B, 1]
            all_attn.append(outputs[1])    # attention_weights [B, N]
        return all_logits, all_attn, self._mc_passes

    def _single_pass(self, feed: dict) -> tuple:
        """Single forward pass fallback."""
        outputs = self._session.run(self._output_names, feed)
        return [outputs[0]], [outputs[1]]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))
