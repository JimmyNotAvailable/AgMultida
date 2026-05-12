from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.core.errors import AgTechError, ErrorCode
from backend.core.schemas import ZoneRegistryEntry

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ZONE_REGISTRY_PATH = PROJECT_ROOT / "metadata" / "zone_registry.csv"
ZONE_GEOJSON_PATH = PROJECT_ROOT / "metadata" / "zones.geojson"


def load_zone_registry() -> list[ZoneRegistryEntry]:
    with ZONE_REGISTRY_PATH.open(newline="", encoding="utf-8") as registry_file:
        return [
            ZoneRegistryEntry(
                zone_id=row["zone_id"],
                zone_name=row["zone_name"],
                province=row["province"],
                crop_type=row["crop_type"],
                split=row["split"],
                local_timezone=row["local_timezone"],
            )
            for row in csv.DictReader(registry_file)
        ]


def load_zone_feature(zone_id: str) -> dict:
    with ZONE_GEOJSON_PATH.open(encoding="utf-8") as geojson_file:
        payload = json.load(geojson_file)
    for feature in payload.get("features", []):
        if feature.get("properties", {}).get("zone_id") == zone_id:
            return feature
    raise AgTechError(
        error_code=ErrorCode.ZONE_NOT_FOUND,
        message="Zone not found",
        status_code=404,
        details={"zone_id": zone_id},
    )


def get_zone_bbox(zone_id: str) -> tuple[float, float, float, float]:
    feature = load_zone_feature(zone_id)
    coordinates = feature["geometry"]["coordinates"][0]
    longitudes = [point[0] for point in coordinates]
    latitudes = [point[1] for point in coordinates]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)
