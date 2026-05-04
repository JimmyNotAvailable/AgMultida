from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "metadata" / "dataset_contract.yaml"


def test_dataset_contract_declares_multimodal_schema_and_shapes():
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))

    required_fields = {field["name"] for field in contract["sample_schema"]}

    assert {
        "sample_id",
        "zone_id",
        "timestamp",
        "timestamp_utc",
        "local_date",
        "local_timezone",
        "image_path",
        "sensor_seq_path",
        "weather_ctx_path",
        "modality_mask",
        "stress_label",
        "cloud_rate",
        "source_trace",
        "source_latest_available_date",
        "source_status",
        "checksum",
    }.issubset(required_fields)
    assert contract["timezone_policy"]["local_timezone"] == "Asia/Ho_Chi_Minh"
    assert contract["timezone_policy"]["storage_timezone"] == "UTC"
    assert contract["timezone_policy"]["no_naive_datetime"] is True
    assert contract["local_utc_boundary_policy"]["example_local_date"] == "2024-01-01"
    assert contract["local_utc_boundary_policy"]["example_utc_start"] == "2023-12-31T17:00:00Z"
    assert contract["local_utc_boundary_policy"]["example_utc_end_exclusive"] == "2024-01-01T17:00:00Z"
    assert "SOURCE_DELAYED" in contract["source_status_values"]
    assert contract["source_status_policy"]["blocked_or_delayed_must_not_pass"] is True
    assert "SOURCE_DELAYED" in contract["source_status_policy"]["source_latest_available_date_required_for"]
    assert contract["tensor_shapes"]["image"] == [4, 224, 224]
    assert contract["tensor_shapes"]["sequence"] == [48, 8]
    assert contract["tensor_shapes"]["label"] == [1]
    assert contract["tensor_shapes"]["modality_mask"] == [3]
