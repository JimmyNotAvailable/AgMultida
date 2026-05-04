"""AI system decision engine: reuses backend evaluate_decision (no duplication).

Guard #2 compliance: single source of truth for decision logic lives in
backend/decision_engine/main.py::evaluate_decision(). This module imports
and re-exports it for AI pipeline consumption without FastAPI dependency.

Both backend wrapper and AI wrapper MUST stay contract-identical.
If thresholds change, update contracts/decision_contract.yaml first,
then update backend/decision_engine/main.py (single source).
"""
from __future__ import annotations

import sys
from pathlib import Path

# JUN: Add backend root so we can import the pure function
_backend_root = str(Path(__file__).resolve().parent.parent / "backend")
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from decision_engine.main import evaluate_decision  # noqa: E402 -- path setup above
from core.schemas import RecommendRequest, IrrigationDecision  # noqa: E402


def make_decision(
    zone_id: str,
    stress_prob: float,
    uncertainty: float,
    degraded_mode: bool,
    soil_moisture: float,
    rain_forecast_3h: float,
    attention_weights: list[float] | None = None,
) -> IrrigationDecision:
    """Convenience wrapper: build RecommendRequest and evaluate.

    This is the AI system's entry point for decision making.
    Delegates entirely to backend/decision_engine/main.py::evaluate_decision.
    """
    req = RecommendRequest(
        zone_id=zone_id,
        stress_prob=stress_prob,
        uncertainty=uncertainty,
        degraded_mode=degraded_mode,
        soil_moisture=soil_moisture,
        rain_forecast_3h=rain_forecast_3h,
        attention_weights=attention_weights or [],
    )
    return evaluate_decision(req)
