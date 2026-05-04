import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZONE_REGISTRY_PATH = PROJECT_ROOT / "metadata" / "zone_registry.csv"
ZONES_GEOJSON_PATH = PROJECT_ROOT / "metadata" / "zones.geojson"


def test_zone_registry_has_required_columns_and_no_fake_primary_data():
    with ZONE_REGISTRY_PATH.open(newline="", encoding="utf-8") as registry_file:
        rows = list(csv.DictReader(registry_file))

    assert rows
    assert set(rows[0]) == {
        "zone_id",
        "zone_name",
        "country",
        "region",
        "province",
        "crop_type",
        "split",
        "synthetic_test_polygon",
        "purpose",
        "not_field_boundary",
        "local_timezone",
        "geometry_source",
        "notes",
    }
    assert {row["zone_id"] for row in rows} == {"A01", "A02", "A03", "D01", "E01", "F01"}
    assert {row["split"] for row in rows} == {"train", "val", "test"}
    assert all(row["synthetic_test_polygon"] == "true" for row in rows)
    assert all(row["purpose"] == "pipeline_validation_only" for row in rows)
    assert all(row["not_field_boundary"] == "true" for row in rows)
    assert all(row["local_timezone"] == "Asia/Ho_Chi_Minh" for row in rows)
    assert all(row["geometry_source"] == "synthetic_validation_polygon" for row in rows)
    assert not any("template" in row["zone_id"] for row in rows)


def test_zones_geojson_matches_realtime_validation_zones():
    with ZONE_REGISTRY_PATH.open(newline="", encoding="utf-8") as registry_file:
        registry_rows = {
            row["zone_id"]: row
            for row in csv.DictReader(registry_file)
        }
    geojson = json.loads(ZONES_GEOJSON_PATH.read_text(encoding="utf-8"))

    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 6
    assert geojson["metadata"]["synthetic_test_polygon"] is True
    assert geojson["metadata"]["purpose"] == "pipeline_validation_only"
    assert geojson["metadata"]["not_field_boundary"] is True

    for feature in geojson["features"]:
        properties = feature["properties"]
        registry_row = registry_rows[properties["zone_id"]]
        assert properties["split"] == registry_row["split"]
        assert properties["province"] == registry_row["province"]
        assert properties["crop_type"] == registry_row["crop_type"]
        assert properties["synthetic_test_polygon"] is True
        assert properties["purpose"] == "pipeline_validation_only"
        assert properties["not_field_boundary"] is True
        assert properties["local_timezone"] == "Asia/Ho_Chi_Minh"
        assert properties["geometry_source"] == "synthetic_validation_polygon"
        assert feature["geometry"]["type"] == "Polygon"
        ring = feature["geometry"]["coordinates"][0]
        assert ring[0] == ring[-1]
        assert len(ring) >= 4
