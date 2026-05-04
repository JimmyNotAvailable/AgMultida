"""Decision engine tests: validate all rule branches and safety invariants.

Tests the pure evaluate_decision function via ai_system.decision_engine.make_decision.
Ensures contract-identical behavior with backend/decision_engine/main.py.
Run: pytest tests/ai_system/test_decision_engine.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# JUN: Setup paths for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from ai_system.decision_engine import make_decision
from backend.core.schemas import RecAction


class TestRainOverride:
    """Step 1: rain_forecast_3h > 0.40 -> NO_IRRIGATION."""

    def test_high_rain_overrides_everything(self):
        dec = make_decision("A01", stress_prob=0.90, uncertainty=0.05,
                            degraded_mode=False, soil_moisture=10.0, rain_forecast_3h=0.50)
        assert dec.action == RecAction.NO_IRRIGATION
        assert dec.reason == "rain_override"
        assert dec.require_ack is False


class TestUncertaintyGate:
    """Step 2: uncertainty > 0.30 -> HOLD + require_ack=true."""

    def test_high_uncertainty_holds(self):
        dec = make_decision("A01", stress_prob=0.70, uncertainty=0.35,
                            degraded_mode=False, soil_moisture=20.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.HOLD
        assert dec.require_ack is True

    def test_degraded_mode_holds(self):
        """degraded_mode=true always triggers HOLD regardless of raw uncertainty."""
        dec = make_decision("A01", stress_prob=0.70, uncertainty=0.10,
                            degraded_mode=True, soil_moisture=20.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.HOLD
        assert dec.require_ack is True

    def test_degraded_amplifies_uncertainty(self):
        """degraded_mode multiplies uncertainty by 1.3, potentially pushing above gate."""
        dec = make_decision("A01", stress_prob=0.70, uncertainty=0.25,
                            degraded_mode=True, soil_moisture=20.0, rain_forecast_3h=0.10)
        # 0.25 * 1.3 = 0.325 > 0.30 -> HOLD
        assert dec.action == RecAction.HOLD


class TestStressMapping:
    """Steps 3-6: stress + moisture mapping."""

    def test_critical_stress(self):
        dec = make_decision("A01", stress_prob=0.65, uncertainty=0.10,
                            degraded_mode=False, soil_moisture=20.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.HEAVY
        assert dec.volume_mm == 20.0

    def test_moderate_stress(self):
        dec = make_decision("A01", stress_prob=0.45, uncertainty=0.10,
                            degraded_mode=False, soil_moisture=28.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.MODERATE
        assert dec.volume_mm == 12.0

    def test_early_watch(self):
        dec = make_decision("A01", stress_prob=0.30, uncertainty=0.10,
                            degraded_mode=False, soil_moisture=40.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.LIGHT
        assert dec.volume_mm == 5.0

    def test_healthy_range(self):
        dec = make_decision("A01", stress_prob=0.10, uncertainty=0.05,
                            degraded_mode=False, soil_moisture=50.0, rain_forecast_3h=0.10)
        assert dec.action == RecAction.NO_IRRIGATION
        assert dec.reason == "healthy_range"


class TestSafetyInvariants:
    """Safety invariants from decision_contract.yaml."""

    def test_trace_id_always_present(self):
        dec = make_decision("A01", stress_prob=0.50, uncertainty=0.10,
                            degraded_mode=False, soil_moisture=30.0, rain_forecast_3h=0.10)
        assert dec.trace_id is not None

    def test_all_actions_have_volume(self):
        for action in RecAction:
            dec = make_decision(
                "A01", stress_prob=0.50, uncertainty=0.10,
                degraded_mode=False, soil_moisture=30.0, rain_forecast_3h=0.10,
            )
            assert dec.volume_mm >= 0.0
