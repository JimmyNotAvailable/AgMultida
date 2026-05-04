# Metadata Readiness Report

## Executive Verdict

METADATA_REALTIME_READY

## AOI

- Country: Vietnam
- Region: Mekong Delta
- Provinces: An Giang, Dong Thap, Can Tho
- Crop type: rice
- Zones: A01, A02, A03, D01, E01, F01
- Splits: train, val, test

## Polygon Disclosure

All six polygons are synthetic validation polygons. Each record is marked with:

- `synthetic_test_polygon=true`
- `purpose=pipeline_validation_only`
- `not_field_boundary=true`

They are not audited field boundaries.

## Historical Backfill

- Start date: 2024-01-01
- End date: 2024-06-30
- Local timezone: Asia/Ho_Chi_Minh
- Storage timezone: UTC

## Source Readiness

- Required: sentinel2, chirps, open_meteo
- Optional preferred: era5_land
- Optional: smap

Auth blockers remain for GEE, CDS, and Earthdata. Real download is not approved in DATA_4A.
