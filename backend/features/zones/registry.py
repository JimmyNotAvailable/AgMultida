from __future__ import annotations

import csv
import json
from pathlib import Path

from core.geospatial import calculate_centroid
from core.schemas import ZoneRegistryEntry
from features.zones.schemas import ZoneBounds, ZoneRegistryItem
from platform_layer.cache import TieredCache, json_decoder, json_encoder

REGISTRY_CACHE_KEY = "registry"


class ZoneRegistryService:
    def __init__(
        self,
        registry_path: Path,
        geojson_path: Path,
        cache: TieredCache[dict] | None = None,
    ) -> None:
        self._registry_path = registry_path
        self._geojson_path = geojson_path
        self._cache = cache

    async def list_zones(self) -> list[ZoneRegistryItem]:
        if self._cache is not None:
            cached = await self._cache.get(REGISTRY_CACHE_KEY, json_decoder)
            if cached is not None:
                return [ZoneRegistryItem.model_validate(item) for item in cached["zones"]]

        zones = self._load_zones()
        if self._cache is not None:
            payload = {"zones": [zone.model_dump(mode="json") for zone in zones]}
            await self._cache.set(REGISTRY_CACHE_KEY, payload, json_encoder)
        return zones

    def _load_zones(self) -> list[ZoneRegistryItem]:
        features = self._load_features_by_zone_id()
        with self._registry_path.open(newline="", encoding="utf-8") as registry_file:
            return [self._build_item(row, self._get_feature(features, row["zone_id"])) for row in csv.DictReader(registry_file)]

    def _load_features_by_zone_id(self) -> dict[str, dict]:
        with self._geojson_path.open(encoding="utf-8") as geojson_file:
            payload = json.load(geojson_file)
        return {feature["properties"]["zone_id"]: feature for feature in payload.get("features", [])}

    def _get_feature(self, features: dict[str, dict], zone_id: str) -> dict:
        feature = features.get(zone_id)
        if feature is None:
            raise RuntimeError(f"Zone feature missing for registry id {zone_id}")
        return feature

    def _build_item(self, row: dict[str, str], feature: dict) -> ZoneRegistryItem:
        coordinates = feature["geometry"]["coordinates"][0]
        longitudes = [point[0] for point in coordinates]
        latitudes = [point[1] for point in coordinates]
        return ZoneRegistryItem(
            zone=ZoneRegistryEntry(
                zone_id=row["zone_id"],
                zone_name=row["zone_name"],
                province=row["province"],
                crop_type=row["crop_type"],
                split=row["split"],
                local_timezone=row["local_timezone"],
            ),
            bounds=ZoneBounds(
                min_lng=min(longitudes),
                min_lat=min(latitudes),
                max_lng=max(longitudes),
                max_lat=max(latitudes),
            ),
            centroid=calculate_centroid(coordinates),
        )
