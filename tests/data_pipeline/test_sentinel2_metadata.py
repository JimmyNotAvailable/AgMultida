from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "metadata" / "source_registry.yaml"


def test_sentinel2_metadata_declares_required_collection_bands_and_outputs():
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    sentinel2 = registry["sources"]["sentinel2_stac"]

    assert sentinel2["provider"] == "STAC"
    assert sentinel2["required"] is True
    assert sentinel2["auth_required"] is False
    assert sentinel2["bands"] == ["B02", "B03", "B04", "B08", "SCL"]
    assert sentinel2["script"] == "scripts/download_sentinel2_stac.py"
    assert "scene_id" in sentinel2["metadata_fields"]
