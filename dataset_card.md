# Dataset Card

## Dataset Name

Multimodal AgTech Water Stress Detection Dataset

## Current Status

Realtime-ready metadata scaffold only. No primary public-source data has been downloaded in Phase 1.

## Intended Modalities

- Sentinel-2 RGB + NIR image patch: `[4, 224, 224]`
- Environmental sequence: `[48, 8]`
- Weather context: `[2..6]`
- Proxy stress label: `[1]`
- Modality mask: `[3]`

## Traceability Requirements

Each final sample must include source trace metadata and SHA-256 checksums for auditable reproduction.

## AOI and Provenance Caveat

The current AOI metadata targets rice zones in Vietnam's Mekong Delta: An Giang, Dong Thap, and Can Tho. The six polygons in `metadata/zones.geojson` are temporary validation polygons only. They are marked as `synthetic_test_polygon=true`, `purpose=pipeline_validation_only`, and `not_field_boundary=true`.

These polygons are not audited field boundaries and must not be used as ground-truth farm geometry.

## Realtime Readiness

The metadata supports two collection modes:

- `historical_backfill`: `2024-01-01` to `2024-06-30`
- `realtime_incremental`: scheduled at `06:00` in `Asia/Ho_Chi_Minh`, with `lookback_days=14`

Storage and source query timestamps use UTC ISO-8601. Local scheduling and `local_date` use `Asia/Ho_Chi_Minh`. Naive datetimes are not allowed.

## Active Source Path

The current collection path is GEE-free. Sentinel-2 is planned through public STAC providers, CHIRPS through the Climate Hazards Center direct repository, and Open-Meteo through its Archive API. GEE adapters are disabled because the project/billing/auth flow is blocking progress.

## Limitations

This card will be generated from processed dataset artifacts in a later phase. Current content documents source and metadata readiness only.
