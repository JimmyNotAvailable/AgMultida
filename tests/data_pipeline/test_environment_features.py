from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "metadata" / "source_registry.yaml"
DATE_RANGE_PATH = PROJECT_ROOT / "metadata" / "date_range.yaml"


def test_environment_sources_include_required_variables():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))

    era5_variables = set(registry["sources"]["era5_land"]["variables"])
    chirps_features = set(registry["sources"]["chirps_direct"]["derived_features"])

    assert {
        "2m_temperature",
        "2m_dewpoint_temperature",
        "skin_temperature",
        "volumetric_soil_water_layer_1",
        "volumetric_soil_water_layer_2",
        "total_precipitation",
        "potential_evaporation",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
    }.issubset(era5_variables)

    assert {
        "rain_1d",
        "rain_3d_sum",
        "rain_7d_sum",
        "dry_spell_days",
        "rain_anomaly_30d",
    }.issubset(chirps_features)


def test_date_range_is_realtime_ready_and_timezone_safe():
    date_range = yaml.safe_load(DATE_RANGE_PATH.read_text(encoding="utf-8"))

    timezone_policy = date_range["timezone_policy"]
    historical = date_range["collection_modes"]["historical_backfill"]
    realtime = date_range["collection_modes"]["realtime_incremental"]

    assert timezone_policy["local_timezone"] == "Asia/Ho_Chi_Minh"
    assert timezone_policy["storage_timezone"] == "UTC"
    assert timezone_policy["timestamp_format"] == "ISO-8601 UTC"
    assert timezone_policy["no_naive_datetime"] is True
    assert historical["enabled"] is True
    assert historical["start_date"] == "2024-01-01"
    assert historical["end_date"] == "2024-06-30"
    assert historical["utc_query_start"] == "2023-12-31T17:00:00Z"
    assert historical["utc_query_end_exclusive"] == "2024-06-30T17:00:00Z"
    assert historical["start_date"] < historical["end_date"]
    assert realtime["enabled"] is True
    assert realtime["run_at_local"] == "06:00"
    assert realtime["lookback_days"] == 14
    assert "latest_available" in realtime["latest_available_policy"]
    assert "SOURCE_DELAYED" in realtime["source_delay_policy"]
    assert date_range["source_status_policy"]["blocked_or_delayed_must_not_pass"] is True


def test_historical_local_dates_map_to_utc_query_boundaries():
    date_range = yaml.safe_load(DATE_RANGE_PATH.read_text(encoding="utf-8"))
    historical = date_range["collection_modes"]["historical_backfill"]
    local_tz = ZoneInfo(date_range["timezone_policy"]["local_timezone"])

    local_start = datetime.fromisoformat(historical["start_date"]).replace(tzinfo=local_tz)
    local_end_exclusive = datetime.fromisoformat("2024-07-01").replace(tzinfo=local_tz)

    assert local_start.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z") == historical["utc_query_start"]
    assert local_end_exclusive.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z") == historical["utc_query_end_exclusive"]
