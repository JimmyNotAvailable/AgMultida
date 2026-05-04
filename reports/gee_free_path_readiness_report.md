# GEE-Free Path Readiness Report

## Executive Verdict

GEE_FREE_PATH_PARTIAL

## New Source Strategy

- Sentinel-2: public STAC provider chain.
- CHIRPS: Climate Hazards Center direct HTTP repository.
- Open-Meteo: Archive API.

GEE Sentinel-2 and CHIRPS adapters are disabled with `GEE_PROJECT_BILLING_BLOCKED`.

## Provider Priority

Sentinel-2:

1. AWS Earth Search STAC
2. Microsoft Planetary Computer STAC
3. Copernicus Data Space STAC if account/token path is available

CHIRPS:

1. Climate Hazards Center direct repository

Open-Meteo:

1. Open-Meteo Archive API

## Required vs Optional Sources

Required:

- sentinel2_stac
- chirps_direct
- open_meteo

Optional:

- era5_land
- smap

Disabled:

- sentinel2_gee
- chirps_gee

## Real Download Gate

No real download has been run. The GEE-free source path is dry-run ready; real-download execution remains intentionally blocked until the exact approval phrase below is provided:

`APPROVE GEE-FREE DATA REAL DOWNLOAD`
