from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "metadata" / "dataset_contract.yaml"


def test_proxy_label_weights_are_traceable_and_sum_to_expected_components():
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    weights = contract["proxy_label"]["weights"]

    assert weights == {
        "soil_moisture_deficit": 0.40,
        "ndvi_anomaly": 0.35,
        "et_deficit": 0.25,
        "rain_relief": -0.15,
        "heat_penalty": 0.15,
    }
    assert contract["proxy_label"]["output_range"] == [0.0, 1.0]
    assert contract["proxy_label"]["trace_required"] is True
