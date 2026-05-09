#!/usr/bin/env python3
"""Build training-ready tensors from downloaded real GEE-free sources."""
from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_SENTINEL_INDEX = PROJECT_ROOT / "data/raw/sentinel2/sentinel2_scene_index.csv"
RAW_OPEN_METEO = PROJECT_ROOT / "data/raw/open_meteo/open_meteo_combined.csv"
ZONES_GEOJSON = PROJECT_ROOT / "metadata/zones.geojson"
OUT_DIR = PROJECT_ROOT / "data/processed_real"
LOCAL_TIMEZONE = "Asia/Ho_Chi_Minh"
BAND_KEYS = ("blue", "green", "red", "nir")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_zone_splits() -> dict[str, str]:
    payload = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
    return {feature["properties"]["zone_id"]: feature["properties"]["split"] for feature in payload["features"]}


def parse_asset_hrefs(value: str) -> dict[str, str]:
    hrefs = ast.literal_eval(value)
    normalized: dict[str, str] = {}
    for key, href in hrefs.items():
        lower = key.lower()
        if lower in BAND_KEYS:
            normalized[lower] = href
        elif lower == "b02":
            normalized["blue"] = href
        elif lower == "b03":
            normalized["green"] = href
        elif lower == "b04":
            normalized["red"] = href
        elif lower == "b08":
            normalized["nir"] = href
    return normalized


def enrich_missing_band_hrefs(scene: pd.Series) -> dict[str, str]:
    hrefs = parse_asset_hrefs(scene["asset_hrefs"])
    if set(BAND_KEYS).issubset(hrefs):
        return hrefs
    scl_href = hrefs.get("scl") or ast.literal_eval(scene["asset_hrefs"]).get("SCL")
    if not scl_href:
        raise ValueError(f"Scene lacks usable Sentinel-2 band hrefs: {scene['scene_id']}")
    base = scl_href.rsplit("/", 1)[0]
    hrefs.update({
        "blue": f"{base}/B02.tif",
        "green": f"{base}/B03.tif",
        "red": f"{base}/B04.tif",
        "nir": f"{base}/B08.tif",
    })
    return hrefs


def read_band_patch(href: str) -> np.ndarray:
    with rasterio.open(href) as dataset:
        band = dataset.read(1, out_shape=(224, 224), resampling=Resampling.bilinear).astype(np.float32)
    band = np.nan_to_num(band, nan=0.0, posinf=0.0, neginf=0.0)
    max_value = float(np.nanmax(band)) if band.size else 0.0
    if max_value > 1.0:
        band = band / 10000.0
    return np.clip(band, 0.0, 1.0).astype(np.float32)


def build_image_tensor(scene: pd.Series) -> np.ndarray:
    hrefs = enrich_missing_band_hrefs(scene)
    bands = [read_band_patch(hrefs[key]) for key in BAND_KEYS]
    return np.stack(bands, axis=0).astype(np.float32)


def normalized(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def weather_for_sample(open_meteo: pd.DataFrame, zone_id: str, local_date: str) -> pd.Series:
    zone_weather = open_meteo[open_meteo["zone_id"] == zone_id].sort_values("time")
    eligible = zone_weather[zone_weather["time"] <= local_date]
    if eligible.empty:
        raise ValueError(f"No weather on or before {local_date} for zone {zone_id}")
    same_day = eligible[eligible["time"] == local_date]
    if not same_day.empty:
        return same_day.iloc[-1]
    return eligible.iloc[-1]


def build_sensor_seq(weather: pd.Series) -> np.ndarray:
    row = np.array([
        normalized(float(weather["precipitation_sum"]), 0.0, 50.0),
        normalized(float(weather["temperature_2m_mean"]), 15.0, 45.0),
        normalized(float(weather["temperature_2m_max"]), 15.0, 45.0),
        normalized(float(weather["relative_humidity_2m_max"]), 0.0, 100.0),
        normalized(float(weather["wind_speed_10m_max"]), 0.0, 40.0),
        normalized(float(weather["shortwave_radiation_sum"]), 0.0, 35.0),
        normalized(float(weather["rain_sum"]), 0.0, 50.0),
        normalized(float(weather["et0_fao_evapotranspiration"]), 0.0, 10.0),
    ], dtype=np.float32)
    return np.tile(row, (48, 1)).astype(np.float32)


def build_weather_ctx(weather: pd.Series) -> np.ndarray:
    return np.array([
        normalized(float(weather["rain_sum"]), 0.0, 50.0),
        normalized(float(weather["precipitation_sum"]), 0.0, 50.0),
        normalized(float(weather["temperature_2m_max"]), 15.0, 45.0),
        normalized(float(weather["temperature_2m_min"]), 10.0, 35.0),
        normalized(float(weather["relative_humidity_2m_max"]), 0.0, 100.0),
        normalized(float(weather["et0_fao_evapotranspiration"]), 0.0, 10.0),
    ], dtype=np.float32)


def build_label(image: np.ndarray, weather: pd.Series) -> float:
    red = image[2]
    nir = image[3]
    ndvi = np.divide(nir - red, nir + red + 1e-6)
    ndvi_stress = float(np.clip((0.55 - float(np.nanmean(ndvi))) / 0.55, 0.0, 1.0))
    heat = normalized(float(weather["temperature_2m_max"]), 30.0, 42.0)
    dryness = 1.0 - normalized(float(weather["precipitation_sum"]), 0.0, 20.0)
    et0 = normalized(float(weather["et0_fao_evapotranspiration"]), 0.0, 8.0)
    label = 0.45 * ndvi_stress + 0.25 * heat + 0.20 * dryness + 0.10 * et0
    return float(np.clip(label, 0.0, 1.0))


def write_sample(sample_dir: Path, image: np.ndarray, sensor_seq: np.ndarray, weather_ctx: np.ndarray) -> dict[str, str]:
    sample_dir.mkdir(parents=True, exist_ok=True)
    image_path = sample_dir / "image.npy"
    sensor_path = sample_dir / "sensor_seq.npy"
    weather_path = sample_dir / "weather_ctx.npy"
    np.save(image_path, image.astype(np.float32))
    np.save(sensor_path, sensor_seq.astype(np.float32))
    np.save(weather_path, weather_ctx.astype(np.float32))
    return {
        "image_path": image_path.relative_to(OUT_DIR).as_posix(),
        "sensor_seq_path": sensor_path.relative_to(OUT_DIR).as_posix(),
        "weather_ctx_path": weather_path.relative_to(OUT_DIR).as_posix(),
        "image_checksum": sha256_file(image_path),
        "sensor_seq_checksum": sha256_file(sensor_path),
        "weather_ctx_checksum": sha256_file(weather_path),
    }


def main() -> int:
    if not RAW_SENTINEL_INDEX.exists():
        raise FileNotFoundError(RAW_SENTINEL_INDEX)
    if not RAW_OPEN_METEO.exists():
        raise FileNotFoundError(RAW_OPEN_METEO)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scene_index = pd.read_csv(RAW_SENTINEL_INDEX)
    open_meteo = pd.read_csv(RAW_OPEN_METEO)
    zone_splits = load_zone_splits()

    rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for _, scene in scene_index.iterrows():
        zone_id = str(scene["zone_id"])
        timestamp = pd.to_datetime(scene["datetime"], utc=True)
        local_timestamp = timestamp.tz_convert(ZoneInfo(LOCAL_TIMEZONE))
        local_date = local_timestamp.date().isoformat()
        sample_id = f"{zone_id}_{timestamp.strftime('%Y%m%d')}_{hashlib.sha1(str(scene['scene_id']).encode()).hexdigest()[:8].upper()}"
        try:
            weather = weather_for_sample(open_meteo, zone_id, local_date)
            image = build_image_tensor(scene)
            sensor_seq = build_sensor_seq(weather)
            weather_ctx = build_weather_ctx(weather)
            label = build_label(image, weather)
            paths = write_sample(OUT_DIR / "samples" / sample_id, image, sensor_seq, weather_ctx)
        except Exception as error:
            failures.append({"sample_id": sample_id, "reason": f"{type(error).__name__}: {error}"})
            continue

        source_trace = {
            "image_source": "sentinel2_stac_aws_earth_search_cog",
            "sensor_sources": ["open_meteo_daily_repeated_48h"],
            "weather_source": "open_meteo_forecast_past_days",
            "label_formula": "ndvi_weather_proxy_v1",
            "alignment_method": "sentinel2_anchor_weather_same_day_no_future",
            "cloud_rate": float(scene["cloud_cover"]),
            "scene_id": str(scene["scene_id"]),
        }
        rows.append({
            "sample_id": sample_id,
            "zone_id": zone_id,
            "split": zone_splits.get(zone_id, "train"),
            "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "local_date": local_date,
            "local_timezone": LOCAL_TIMEZONE,
            "image_path": paths["image_path"],
            "sensor_seq_path": paths["sensor_seq_path"],
            "weather_ctx_path": paths["weather_ctx_path"],
            "modality_mask": "[1.0, 1.0, 1.0]",
            "label": label,
            "cloud_rate": float(scene["cloud_cover"]) / 100.0,
            "source_trace": json.dumps(source_trace, sort_keys=True),
            "source_latest_available_date": local_date,
            "source_status": "PASS",
            "image_checksum": paths["image_checksum"],
            "sensor_seq_checksum": paths["sensor_seq_checksum"],
            "weather_ctx_checksum": paths["weather_ctx_checksum"],
            "checksum": paths["image_checksum"],
        })

    manifest = pd.DataFrame(rows)
    if manifest.empty:
        raise RuntimeError(f"No samples built. Failures: {failures[:5]}")

    manifest.to_csv(OUT_DIR / "sample_manifest.csv", index=False)
    for split in ["train", "val", "test"]:
        split_df = manifest[manifest["split"] == split]
        if split_df.empty:
            raise RuntimeError(f"Missing split {split}; built splits={manifest['split'].value_counts().to_dict()}")
        split_df.to_csv(OUT_DIR / f"{split}_manifest.csv", index=False)

    report = {
        "status": "REAL_DERIVED_TRAINING_DATA_READY",
        "sample_count": int(len(manifest)),
        "split_counts": manifest["split"].value_counts().to_dict(),
        "failures": failures,
        "source_limitations": "Sentinel-2 COGs read as 224x224 scene-level patches; labels are proxy labels, not field ground truth.",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUT_DIR / "dataset_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
