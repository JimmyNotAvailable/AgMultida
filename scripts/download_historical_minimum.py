#!/usr/bin/env python3
"""Download minimum historical metadata needed to expand training samples."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests
import yaml
from pystac_client import Client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATE_RANGE_PATH = PROJECT_ROOT / "metadata/date_range.yaml"
ZONES_PATH = PROJECT_ROOT / "metadata/zones.geojson"
SENTINEL_DIR = PROJECT_ROOT / "data/raw/sentinel2"
OPEN_METEO_DIR = PROJECT_ROOT / "data/raw/open_meteo"


def load_history_window() -> tuple[str, str]:
    payload = yaml.safe_load(DATE_RANGE_PATH.read_text(encoding="utf-8"))
    historical = payload["collection_modes"]["historical_backfill"]
    return historical["start_date"], historical["end_date"]


def load_zones() -> list[dict]:
    payload = json.loads(ZONES_PATH.read_text(encoding="utf-8"))
    return payload["features"]


def bbox_from_feature(feature: dict) -> tuple[float, float, float, float]:
    coords = feature["geometry"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def collect_sentinel_history(start_date: str, end_date: str) -> dict[str, object]:
    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open("https://earth-search.aws.element84.com/v1")
    rows: list[dict[str, object]] = []
    for zone in load_zones():
        zone_id = zone["properties"]["zone_id"]
        bbox = bbox_from_feature(zone)
        search = client.search(
            collections=["sentinel-2-c1-l2a"],
            bbox=bbox,
            datetime=f"{start_date}/{end_date}",
            max_items=200,
            query={"eo:cloud_cover": {"lt": 60}},
        )
        for item in search.items():
            assets = {}
            for key in ["blue", "green", "red", "nir", "scl"]:
                if key in item.assets:
                    assets[key] = item.assets[key].href
            rows.append(
                {
                    "scene_id": item.id,
                    "datetime": item.datetime.isoformat() if item.datetime else str(item.properties.get("datetime")),
                    "cloud_cover": item.properties.get("eo:cloud_cover", item.properties.get("s2:cloud_probability")),
                    "zone_id": zone_id,
                    "provider": "aws_earth_search",
                    "bbox": list(bbox),
                    "bands_available": list(assets.keys()),
                    "asset_hrefs": str(assets),
                }
            )
    df = pd.DataFrame(rows).drop_duplicates(subset=["scene_id", "zone_id"]).sort_values(["zone_id", "datetime"])
    output = SENTINEL_DIR / "sentinel2_scene_index.csv"
    df.to_csv(output, index=False)
    catalog = {
        "source": "sentinel2_stac_historical",
        "start_date": start_date,
        "end_date": end_date,
        "items_found": int(len(df)),
        "zones": sorted(df["zone_id"].unique().tolist()) if not df.empty else [],
    }
    (SENTINEL_DIR / "sentinel2_stac_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return {"rows": int(len(df)), "output": str(output)}


def collect_open_meteo_history(start_date: str, end_date: str) -> dict[str, object]:
    OPEN_METEO_DIR.mkdir(parents=True, exist_ok=True)
    zones = load_zones()
    daily_vars = [
        "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
        "relative_humidity_2m_max", "relative_humidity_2m_min",
        "dew_point_2m_min", "dew_point_2m_max",
        "precipitation_sum", "rain_sum",
        "wind_speed_10m_max", "shortwave_radiation_sum", "et0_fao_evapotranspiration",
    ]
    all_frames = []
    for zone in zones:
        zone_id = zone["properties"]["zone_id"]
        bbox = bbox_from_feature(zone)
        lat = (bbox[1] + bbox[3]) / 2
        lon = (bbox[0] + bbox[2]) / 2
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(daily_vars),
            "timezone": "UTC",
        }
        resp = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        (OPEN_METEO_DIR / f"open_meteo_{zone_id}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        daily = data["daily"]
        df = pd.DataFrame(daily)
        df.insert(0, "zone_id", zone_id)
        df.insert(1, "latitude", lat)
        df.insert(2, "longitude", lon)
        df.to_csv(OPEN_METEO_DIR / f"open_meteo_{zone_id}.csv", index=False)
        all_frames.append(df)
    combined = pd.concat(all_frames, ignore_index=True)
    combined_path = OPEN_METEO_DIR / "open_meteo_combined.csv"
    combined.to_csv(combined_path, index=False)
    return {"rows": int(len(combined)), "output": str(combined_path)}


def main() -> int:
    start_date, end_date = load_history_window()
    sentinel = collect_sentinel_history(start_date, end_date)
    open_meteo = collect_open_meteo_history(start_date, end_date)
    print(json.dumps({"start_date": start_date, "end_date": end_date, "sentinel": sentinel, "open_meteo": open_meteo}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
