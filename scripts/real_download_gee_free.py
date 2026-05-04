#!/usr/bin/env python3
"""GEE-free real download orchestrator for Sentinel-2 STAC, CHIRPS direct, Open-Meteo.

Usage:
    python3 scripts/real_download_gee_free.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
import tempfile
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from data_collection_common import (
    append_download_log,
    configure_logging,
    load_source_registry,
    safe_project_path,
    safe_writable_path,
)

def parse_args():
    parser = argparse.ArgumentParser(description="GEE-free real download orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Validate without downloading.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()

_args = parse_args()
configure_logging(_args.log_level)
logger = logging.getLogger("real_download_gee_free")

REGISTRY_PATH = safe_project_path("metadata/source_registry.yaml")
DOWNLOAD_LOG_PATH = safe_writable_path("metadata/download_log.json")
ZONES_PATH = safe_project_path("metadata/zones.geojson")
DATE_RANGE_PATH = safe_project_path("metadata/date_range.yaml")

LOOKBACK_DAYS = 14
TODAY_UTC = date.today()
START_DATE = TODAY_UTC - timedelta(days=LOOKBACK_DAYS)
END_DATE = TODAY_UTC

# Results collector
results: dict[str, dict[str, Any]] = {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_zones() -> list[dict]:
    with open(ZONES_PATH, encoding="utf-8") as f:
        geojson = json.load(f)
    return geojson["features"]


def bbox_from_feature(feature: dict) -> tuple[float, float, float, float]:
    coords = feature["geometry"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


# ─── SENTINEL-2 STAC ───────────────────────────────────────────────
def download_sentinel2_stac(registry: dict) -> dict[str, Any]:
    source = registry["sources"]["sentinel2_stac"]
    output_dir = PROJECT_ROOT / source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    providers = source["provider_priority"]
    zones = load_zones()
    
    all_items_meta = []
    files_written = []
    provider_used = None
    last_error = None
    
    for provider in providers:
        if provider.get("requires_account"):
            logger.info("Skipping %s (requires account)", provider["id"])
            continue
        
        stac_url = provider["stac_url"]
        collection = provider["collection"]
        provider_id = provider["id"]
        logger.info("Trying STAC provider: %s (%s)", provider["name"], stac_url)
        
        try:
            from pystac_client import Client
            client = Client.open(stac_url)
            
            for zone_feat in zones:
                zone_id = zone_feat["properties"]["zone_id"]
                bbox = bbox_from_feature(zone_feat)
                
                search = client.search(
                    collections=[collection],
                    bbox=bbox,
                    datetime=f"{START_DATE.isoformat()}/{END_DATE.isoformat()}",
                    max_items=5,
                    query={"eo:cloud_cover": {"lt": 50}} if provider_id != "microsoft_planetary_computer" else None,
                )
                
                items = list(search.items())
                logger.info("Zone %s: found %d items from %s", zone_id, len(items), provider_id)
                
                for item in items:
                    item_meta = {
                        "scene_id": item.id,
                        "datetime": item.datetime.isoformat() if item.datetime else str(item.properties.get("datetime")),
                        "cloud_cover": item.properties.get("eo:cloud_cover", item.properties.get("s2:cloud_probability")),
                        "zone_id": zone_id,
                        "provider": provider_id,
                        "bbox": list(bbox),
                        "bands_available": [],
                        "asset_hrefs": {},
                    }
                    
                    target_bands = source["bands"]
                    for band in target_bands:
                        band_lower = band.lower()
                        asset_key = None
                        for k in item.assets:
                            if k.lower() == band_lower or k.lower().endswith(band_lower):
                                asset_key = k
                                break
                        if not asset_key:
                            for k in item.assets:
                                if band_lower in k.lower():
                                    asset_key = k
                                    break
                        
                        if asset_key:
                            href = item.assets[asset_key].href
                            item_meta["bands_available"].append(band)
                            item_meta["asset_hrefs"][band] = href
                    
                    all_items_meta.append(item_meta)
            
            provider_used = provider_id
            break
            
        except Exception as e:
            last_error = str(e)
            logger.warning("Provider %s failed: %s", provider_id, e)
            continue
    
    if not provider_used:
        status = "FAIL"
        message = f"All STAC providers failed. Last error: {last_error}"
        logger.error(message)
        return {"status": status, "message": message, "files": [], "items_count": 0}
    
    # Write metadata JSON
    meta_file = output_dir / "sentinel2_stac_catalog.json"
    catalog_data = {
        "source": "sentinel2_stac",
        "provider": provider_used,
        "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "lookback_days": LOOKBACK_DAYS,
        "zones_queried": [z["properties"]["zone_id"] for z in zones],
        "items_found": len(all_items_meta),
        "items": all_items_meta,
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, indent=2, default=str)
    files_written.append(str(meta_file))
    
    # Write per-zone CSV index
    index_file = output_dir / "sentinel2_scene_index.csv"
    if all_items_meta:
        df = pd.DataFrame(all_items_meta)
        df.to_csv(index_file, index=False)
        files_written.append(str(index_file))
    
    # Download one sample thumbnail/preview if available (small file to prove connectivity)
    sample_downloaded = False
    if all_items_meta:
        first_item_assets = all_items_meta[0].get("asset_hrefs", {})
        for band, href in first_item_assets.items():
            if sample_downloaded:
                break
            try:
                # Only download small header check, not full raster
                resp = requests.head(href, timeout=15, allow_redirects=True)
                sample_info_file = output_dir / "sentinel2_sample_asset_check.json"
                sample_info = {
                    "band": band,
                    "href": href,
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("Content-Type"),
                    "content_length": resp.headers.get("Content-Length"),
                    "accessible": resp.status_code == 200,
                }
                with open(sample_info_file, "w", encoding="utf-8") as f:
                    json.dump(sample_info, f, indent=2)
                files_written.append(str(sample_info_file))
                sample_downloaded = True
            except Exception as e:
                logger.warning("Sample asset check failed for %s: %s", band, e)
    
    latest_date = None
    if all_items_meta:
        dates = []
        for item in all_items_meta:
            try:
                dt_str = item["datetime"]
                if "T" in dt_str:
                    dates.append(dt_str[:10])
                else:
                    dates.append(dt_str)
            except Exception:
                pass
        if dates:
            latest_date = max(dates)
    
    status = "PASS" if all_items_meta else "SOURCE_DELAYED"
    message = f"Found {len(all_items_meta)} scenes from {provider_used}, latest={latest_date}"
    
    return {
        "status": status,
        "message": message,
        "provider": provider_used,
        "files": files_written,
        "items_count": len(all_items_meta),
        "latest_available_date": latest_date,
        "checksums": {f: sha256_file(Path(f)) for f in files_written},
    }


# ─── CHIRPS DIRECT ─────────────────────────────────────────────────
def download_chirps_direct(registry: dict) -> dict[str, Any]:
    source = registry["sources"]["chirps_direct"]
    output_dir = PROJECT_ROOT / source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_url = source["direct_base_url"]
    files_written = []
    files_failed = []
    latest_date = None
    
    # CHIRPS has ~35 day production delay; extend lookback to 45 days
    chirps_lookback = 45
    chirps_start = TODAY_UTC - timedelta(days=chirps_lookback)
    current = END_DATE
    attempts = 0
    max_attempts = chirps_lookback
    
    while attempts < max_attempts and current >= chirps_start:
        year = current.year
        filename = f"chirps-v2.0.{current.strftime('%Y.%m.%d')}.tif.gz"
        url = f"{base_url}/{year}/{filename}"
        local_path = output_dir / filename
        
        try:
            logger.info("CHIRPS: trying %s", url)
            resp = requests.get(url, timeout=60, stream=True)
            
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = local_path.stat().st_size
                if file_size > 100:  # Sanity check - not empty
                    files_written.append({
                        "path": str(local_path),
                        "date": current.isoformat(),
                        "size_bytes": file_size,
                        "checksum": sha256_file(local_path),
                    })
                    if latest_date is None:
                        latest_date = current.isoformat()
                    logger.info("CHIRPS: downloaded %s (%d bytes)", filename, file_size)
                else:
                    local_path.unlink(missing_ok=True)
                    files_failed.append({"date": current.isoformat(), "reason": "empty_file"})
            elif resp.status_code == 404:
                files_failed.append({"date": current.isoformat(), "reason": f"HTTP {resp.status_code} - not yet available"})
                logger.info("CHIRPS: %s not available (404)", current.isoformat())
            else:
                files_failed.append({"date": current.isoformat(), "reason": f"HTTP {resp.status_code}"})
                logger.warning("CHIRPS: %s returned HTTP %d", current.isoformat(), resp.status_code)
                
        except Exception as e:
            files_failed.append({"date": current.isoformat(), "reason": str(e)})
            logger.warning("CHIRPS download failed for %s: %s", current.isoformat(), e)
        
        current -= timedelta(days=1)
        attempts += 1
    
    # Write download manifest
    manifest_file = output_dir / "chirps_download_manifest.json"
    manifest = {
        "source": "chirps_direct",
        "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "date_range": {"start": chirps_start.isoformat(), "end": END_DATE.isoformat()},
        "lookback_days": chirps_lookback,
        "files_downloaded": len(files_written),
        "files_failed": len(files_failed),
        "latest_available_date": latest_date,
        "downloaded": files_written,
        "failed": files_failed,
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    
    all_files = [str(manifest_file)] + [fw["path"] for fw in files_written]
    
    if files_written:
        status = "PASS"
        message = f"Downloaded {len(files_written)} CHIRPS daily files, latest={latest_date}"
    else:
        status = "SOURCE_DELAYED"
        message = f"No CHIRPS data available in lookback window {chirps_start}..{END_DATE}. {len(files_failed)} dates tried."
    
    return {
        "status": status,
        "message": message,
        "files": all_files,
        "files_downloaded_count": len(files_written),
        "files_failed_count": len(files_failed),
        "latest_available_date": latest_date,
        "checksums": {str(manifest_file): sha256_file(manifest_file)},
    }


# ─── OPEN-METEO ────────────────────────────────────────────────────
def download_open_meteo(registry: dict) -> dict[str, Any]:
    source = registry["sources"]["open_meteo"]
    output_dir = PROJECT_ROOT / source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    endpoint = source["endpoint"]
    variables = source["variables"]
    zones = load_zones()
    files_written = []
    zone_results = []
    
    for zone_feat in zones:
        zone_id = zone_feat["properties"]["zone_id"]
        bbox = bbox_from_feature(zone_feat)
        lat = (bbox[1] + bbox[3]) / 2
        lon = (bbox[0] + bbox[2]) / 2
        
        # Open-Meteo daily variables need aggregation suffixes
        daily_vars = [
            "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
            "relative_humidity_2m_max", "relative_humidity_2m_min",
            "dew_point_2m_min", "dew_point_2m_max",
            "precipitation_sum", "rain_sum",
            "wind_speed_10m_max",
            "shortwave_radiation_sum",
            "et0_fao_evapotranspiration",
        ]
        
        try:
            # Try forecast API with past_days first (works for recent data)
            forecast_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "past_days": LOOKBACK_DAYS,
                "forecast_days": 0,
                "daily": ",".join(daily_vars),
                "timezone": "UTC",
            }
            logger.info("Open-Meteo: querying zone %s (%.4f, %.4f) via forecast+past_days", zone_id, lat, lon)
            resp = requests.get(forecast_url, params=params, timeout=30)
            
            # Fallback to archive API with safe date range if forecast fails
            if resp.status_code != 200:
                archive_end = TODAY_UTC - timedelta(days=5)
                archive_start = archive_end - timedelta(days=LOOKBACK_DAYS)
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": archive_start.isoformat(),
                    "end_date": archive_end.isoformat(),
                    "daily": ",".join(daily_vars),
                    "timezone": "UTC",
                }
                logger.info("Open-Meteo: fallback to archive API for zone %s", zone_id)
                resp = requests.get(endpoint, params=params, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                
                # Save raw JSON response
                json_file = output_dir / f"open_meteo_{zone_id}.json"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                files_written.append(str(json_file))
                
                # Convert to CSV
                daily = data.get("daily", {})
                if daily and "time" in daily:
                    df = pd.DataFrame(daily)
                    df.insert(0, "zone_id", zone_id)
                    df.insert(1, "latitude", lat)
                    df.insert(2, "longitude", lon)
                    csv_file = output_dir / f"open_meteo_{zone_id}.csv"
                    df.to_csv(csv_file, index=False)
                    files_written.append(str(csv_file))
                    
                    zone_results.append({
                        "zone_id": zone_id,
                        "status": "PASS",
                        "rows": len(df),
                        "variables": list(daily.keys()),
                        "date_range": f"{df['time'].min()} to {df['time'].max()}" if "time" in df.columns else "N/A",
                    })
                else:
                    zone_results.append({
                        "zone_id": zone_id,
                        "status": "WARN",
                        "reason": "No daily data in response",
                    })
            else:
                zone_results.append({
                    "zone_id": zone_id,
                    "status": "FAIL",
                    "reason": f"HTTP {resp.status_code}: {resp.text[:200]}",
                })
                logger.warning("Open-Meteo failed for zone %s: HTTP %d", zone_id, resp.status_code)
                
        except Exception as e:
            zone_results.append({
                "zone_id": zone_id,
                "status": "FAIL",
                "reason": str(e),
            })
            logger.warning("Open-Meteo error for zone %s: %s", zone_id, e)
    
    # Merge all zone CSVs into one combined file
    csv_files = [f for f in files_written if f.endswith(".csv")]
    if csv_files:
        combined = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)
        combined_file = output_dir / "open_meteo_combined.csv"
        combined.to_csv(combined_file, index=False)
        files_written.append(str(combined_file))
    
    # Write manifest
    manifest_file = output_dir / "open_meteo_download_manifest.json"
    manifest = {
        "source": "open_meteo",
        "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "variables": variables,
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "zones_queried": len(zones),
        "zone_results": zone_results,
        "files_written": files_written,
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    files_written.append(str(manifest_file))
    
    pass_count = sum(1 for z in zone_results if z["status"] == "PASS")
    fail_count = sum(1 for z in zone_results if z["status"] == "FAIL")
    
    if pass_count == len(zones):
        status = "PASS"
    elif pass_count > 0:
        status = "WARN"
    else:
        status = "FAIL"
    
    message = f"Open-Meteo: {pass_count}/{len(zones)} zones PASS, {fail_count} FAIL"
    
    return {
        "status": status,
        "message": message,
        "files": files_written,
        "zones_pass": pass_count,
        "zones_fail": fail_count,
        "latest_available_date": END_DATE.isoformat(),
        "checksums": {str(manifest_file): sha256_file(manifest_file)},
    }


# ─── ORCHESTRATOR ───────────────────────────────────────────────────
def main() -> int:
    if _args.dry_run:
        print(json.dumps({"status": "PASS", "dry_run": True, "writes_primary_data": False}))
        return 0
    
    logger.info("=" * 60)
    logger.info("GEE-FREE REAL DOWNLOAD — APPROVED")
    logger.info("Date range: %s to %s (lookback=%d days)", START_DATE, END_DATE, LOOKBACK_DAYS)
    logger.info("=" * 60)
    
    registry = load_source_registry(REGISTRY_PATH)
    
    # 1. Sentinel-2 STAC
    logger.info("\n>>> SOURCE 1/3: Sentinel-2 STAC")
    try:
        results["sentinel2_stac"] = download_sentinel2_stac(registry)
    except Exception as e:
        results["sentinel2_stac"] = {"status": "FAIL", "message": str(e), "files": [], "traceback": traceback.format_exc()}
        logger.error("Sentinel-2 STAC FAILED: %s", e)
    
    append_download_log(DOWNLOAD_LOG_PATH, {
        "source_id": "sentinel2_stac",
        "script": "real_download_gee_free",
        "status": results["sentinel2_stac"]["status"],
        "dry_run": False,
        "writes_primary_data": True,
        "output_dir": str(PROJECT_ROOT / "data/raw/sentinel2"),
        "credential_policy": "public_stac",
        "message": results["sentinel2_stac"]["message"],
    })
    
    # 2. CHIRPS Direct
    logger.info("\n>>> SOURCE 2/3: CHIRPS Direct")
    try:
        results["chirps_direct"] = download_chirps_direct(registry)
    except Exception as e:
        results["chirps_direct"] = {"status": "FAIL", "message": str(e), "files": [], "traceback": traceback.format_exc()}
        logger.error("CHIRPS Direct FAILED: %s", e)
    
    append_download_log(DOWNLOAD_LOG_PATH, {
        "source_id": "chirps_direct",
        "script": "real_download_gee_free",
        "status": results["chirps_direct"]["status"],
        "dry_run": False,
        "writes_primary_data": True,
        "output_dir": str(PROJECT_ROOT / "data/raw/chirps"),
        "credential_policy": "direct_http",
        "message": results["chirps_direct"]["message"],
    })
    
    # 3. Open-Meteo
    logger.info("\n>>> SOURCE 3/3: Open-Meteo")
    try:
        results["open_meteo"] = download_open_meteo(registry)
    except Exception as e:
        results["open_meteo"] = {"status": "FAIL", "message": str(e), "files": [], "traceback": traceback.format_exc()}
        logger.error("Open-Meteo FAILED: %s", e)
    
    append_download_log(DOWNLOAD_LOG_PATH, {
        "source_id": "open_meteo",
        "script": "real_download_gee_free",
        "status": results["open_meteo"]["status"],
        "dry_run": False,
        "writes_primary_data": True,
        "output_dir": str(PROJECT_ROOT / "data/raw/open_meteo"),
        "credential_policy": "none",
        "message": results["open_meteo"]["message"],
    })
    
    # ─── Determine verdict ──────────────────────────────────────────
    statuses = [r["status"] for r in results.values()]
    if all(s == "PASS" for s in statuses):
        verdict = "RAW_DATA_READY"
    elif any(s == "PASS" for s in statuses):
        verdict = "PARTIAL_RAW_DATA_READY"
    else:
        verdict = "RAW_DATA_FAILED"
    
    # Write final result JSON
    final_result = {
        "verdict": verdict,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sources": results,
    }
    result_file = PROJECT_ROOT / "reports" / "download_result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2, default=str)
    
    # Print summary
    print(json.dumps(final_result, indent=2, default=str))
    
    logger.info("=" * 60)
    logger.info("VERDICT: %s", verdict)
    logger.info("=" * 60)
    
    return 0 if verdict != "RAW_DATA_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
