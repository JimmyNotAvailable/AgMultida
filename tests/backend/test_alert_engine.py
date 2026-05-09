from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from decision_engine.alert_engine import AlertEvaluationInput, AlertRepository, evaluate_alerts


NOW = datetime(2026, 5, 9, 8, 0, tzinfo=timezone.utc)


def test_critical_rule_emits_alert():
    alerts = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=24.9, rain_forecast_3h=0.19), AlertRepository())
    assert alerts[0].severity == "critical"
    assert alerts[0].rule_id == "critical_stress_low_moisture"


def test_warning_rule_emits_alert():
    alerts = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.41, soil_moisture=29.9, rain_forecast_3h=0.5), AlertRepository())
    assert alerts[0].severity == "warning"
    assert alerts[0].rule_id == "warning_stress_low_moisture"


def test_info_rule_emits_when_imagery_stale_more_than_7_days():
    alerts = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.1, soil_moisture=40, rain_forecast_3h=0.5, imagery_acquisition_time=NOW - timedelta(days=7, seconds=1)), AlertRepository())
    assert alerts[0].severity == "info"
    assert alerts[0].rule_id == "imagery_stale"


def test_degraded_rule_emits_when_sensor_missing_more_than_2_hours():
    alerts = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.1, soil_moisture=40, rain_forecast_3h=0.5, sensor_last_seen=NOW - timedelta(hours=2, seconds=1)), AlertRepository())
    assert alerts[0].severity == "degraded"
    assert alerts[0].rule_id == "sensor_missing"


def test_rule_thresholds_are_strict_edges():
    critical_prob_edge = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.6, soil_moisture=24.9, rain_forecast_3h=0.19), AlertRepository())
    assert len(critical_prob_edge) == 1
    assert critical_prob_edge[0].rule_id == "warning_stress_low_moisture"
    assert evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.4, soil_moisture=29.9, rain_forecast_3h=0.19), AlertRepository()) == []
    assert evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.41, soil_moisture=30, rain_forecast_3h=0.19), AlertRepository()) == []
    assert evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.1, soil_moisture=40, rain_forecast_3h=0.5, imagery_acquisition_time=NOW - timedelta(days=7)), AlertRepository()) == []
    assert evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.1, soil_moisture=40, rain_forecast_3h=0.5, sensor_last_seen=NOW - timedelta(hours=2)), AlertRepository()) == []


def test_critical_partial_edges_fall_back_to_warning():
    moisture_edge = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=25, rain_forecast_3h=0.19), AlertRepository())
    rain_edge = evaluate_alerts(AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=24.9, rain_forecast_3h=0.2), AlertRepository())
    assert moisture_edge[0].rule_id == "warning_stress_low_moisture"
    assert rain_edge[0].rule_id == "warning_stress_low_moisture"


def test_multiple_independent_rules_emit_together():
    alerts = evaluate_alerts(
        AlertEvaluationInput(
            zone_id="A01",
            timestamp=NOW,
            stress_prob=0.61,
            soil_moisture=24.9,
            rain_forecast_3h=0.19,
            imagery_acquisition_time=NOW - timedelta(days=7, seconds=1),
            sensor_last_seen=NOW - timedelta(hours=2, seconds=1),
        ),
        AlertRepository(),
    )
    assert [alert.rule_id for alert in alerts] == ["critical_stress_low_moisture", "imagery_stale", "sensor_missing"]


def test_dedupe_suppresses_same_zone_rule_inside_one_hour():
    repository = AlertRepository()
    request = AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=24.9, rain_forecast_3h=0.19)
    assert len(evaluate_alerts(request, repository)) == 1
    assert evaluate_alerts(request.model_copy(update={"timestamp": NOW + timedelta(minutes=59)}), repository) == []


def test_dedupe_allows_same_rule_after_one_hour():
    repository = AlertRepository()
    request = AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=24.9, rain_forecast_3h=0.19)
    assert len(evaluate_alerts(request, repository)) == 1
    assert len(evaluate_alerts(request.model_copy(update={"timestamp": NOW + timedelta(hours=1, seconds=1)}), repository)) == 1


def test_dedupe_keeps_different_zone_and_rule_separate():
    repository = AlertRepository()
    critical = AlertEvaluationInput(zone_id="A01", timestamp=NOW, stress_prob=0.61, soil_moisture=24.9, rain_forecast_3h=0.19)
    warning_other_zone = AlertEvaluationInput(zone_id="A02", timestamp=NOW, stress_prob=0.41, soil_moisture=29.9, rain_forecast_3h=0.5)
    assert len(evaluate_alerts(critical, repository)) == 1
    assert len(evaluate_alerts(warning_other_zone, repository)) == 1
