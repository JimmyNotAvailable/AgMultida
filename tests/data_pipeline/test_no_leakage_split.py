from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "metadata" / "dataset_contract.yaml"


def test_alignment_and_split_contract_prevents_lookahead_leakage():
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["alignment"]["anchor"] == "sentinel2_timestamp_t0"
    assert contract["alignment"]["sequence_window"] == "[t0-48h, t0]"
    assert contract["alignment"]["allow_future_features"] is False
    assert contract["alignment"]["missing_artifact_value"] is None
    assert contract["splits"]["leakage_policy"] == "no_zone_time_overlap"
