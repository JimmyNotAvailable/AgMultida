"""Probability calibration for stress model output.

Stub implementation: identity mapping until IsotonicRegression is fitted
after GATE_5_DATA_QA with real validation data. Interface is locked --
fit() and predict() signatures must not change.

Trade-off: IsotonicRegression is non-parametric and fits well to DL
calibration curves, but requires a held-out calibration set (typically
the validation set). Platt Scaling (logistic) is smoother but assumes
sigmoid shape which may not hold for multimodal fusion output.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("agtech.calibration")

try:
    from sklearn.isotonic import IsotonicRegression
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


class StressCalibrator:
    """Calibrate raw stress probabilities to well-calibrated outputs.

    Before fitting, acts as identity (pass-through).
    After fit(), uses IsotonicRegression for monotonic calibration.
    """

    def __init__(self) -> None:
        self._fitted = False
        self._calibrator: Optional[object] = None

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, raw_probs: np.ndarray, true_labels: np.ndarray) -> None:
        """Fit calibrator on validation set.

        Args:
            raw_probs: [N] raw sigmoid probabilities from model.
            true_labels: [N] binary ground truth labels.
        """
        if not _HAS_SKLEARN:
            logger.warning(
                "scikit-learn not available, calibrator remains in stub mode"
            )
            return

        calibrator = IsotonicRegression(
            y_min=0.0, y_max=1.0, out_of_bounds="clip",
        )
        calibrator.fit(raw_probs, true_labels)
        self._calibrator = calibrator
        self._fitted = True
        logger.info("Calibrator fitted on %d samples", len(raw_probs))

    def predict(self, raw_probs: np.ndarray) -> np.ndarray:
        """Calibrate probabilities.

        Args:
            raw_probs: [N] or [B,1] raw probabilities.

        Returns:
            Calibrated probabilities, same shape as input.
        """
        original_shape = raw_probs.shape
        flat = raw_probs.ravel()

        if not self._fitted:
            # Stub mode: identity pass-through
            return raw_probs

        calibrated = self._calibrator.predict(flat)  # type: ignore[union-attr]
        return calibrated.reshape(original_shape)

    def save(self, path: str) -> None:
        """Persist fitted calibrator to disk."""
        import joblib
        if not self._fitted:
            logger.warning("Saving unfitted calibrator")
        joblib.dump(self._calibrator, path)

    @classmethod
    def load(cls, path: str) -> "StressCalibrator":
        """Load previously fitted calibrator."""
        import joblib
        instance = cls()
        instance._calibrator = joblib.load(path)
        instance._fitted = instance._calibrator is not None
        return instance
