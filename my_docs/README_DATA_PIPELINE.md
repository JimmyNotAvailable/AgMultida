# Data Collection and Processing Runbook

This runbook summarizes the Phase 1 dataset pipeline for multimodal water stress monitoring. It covers public-source data collection and the downstream processing boundary before model training.

## Scope

This scaffold does not contain production credentials or downloaded primary data.

The current DATA_4A metadata targets Vietnam's Mekong Delta for pipeline validation:

- Provinces: An Giang, Dong Thap, Can Tho
- Crop type: rice
- Zones: A01, A02, A03, D01, E01, F01
- Splits: train, val, test

The zone polygons are temporary validation polygons. They are explicitly marked with `synthetic_test_polygon=true`, `purpose=pipeline_validation_only`, and `not_field_boundary=true`. They must not be treated as audited field boundaries.

## Collection Modes

`historical_backfill` is enabled for Phase 1 validation from `2024-01-01` through `2024-06-30`.

`realtime_incremental` is enabled as metadata for future scheduled ingestion. It is configured for local scheduling at `06:00` in `Asia/Ho_Chi_Minh` with a `14` day lookback window. If a source has no data for the current local date, the pipeline must search backward and set `latest_available_date`; it must not mark delayed data as `PASS`.

## Timezone Policy

- Scheduling and `local_date`: `Asia/Ho_Chi_Minh`
- Storage, query windows, logs, and dataset contract timestamps: UTC ISO-8601
- Naive datetimes are not allowed.

## Sources

- Sentinel-2 Surface Reflectance Harmonized from Google Earth Engine.
- ERA5-Land from Copernicus Climate Data Store.
- CHIRPS Daily precipitation from Google Earth Engine.
- SMAP SPL3SMP_E from NASA Earthdata / NSIDC, with a fallback path to Google Earth Engine.
- Open-Meteo Archive API for fallback or cross-check weather context.

Required sources are Sentinel-2, CHIRPS, and Open-Meteo. ERA5-Land is optional preferred. SMAP is optional.

The active DATA_4C path is GEE-free:

- Sentinel-2 uses STAC providers in this priority order: AWS Earth Search, Microsoft Planetary Computer, then Copernicus Data Space if an account path is configured.
- CHIRPS uses Climate Hazards Center direct HTTP download.
- Open-Meteo uses the Archive API directly.

The previous GEE adapters remain disabled with `disabled_reason=GEE_PROJECT_BILLING_BLOCKED` and must not block dry-run or minimum viable real download.

Allowed source statuses are `PASS`, `WARN`, `FAIL`, `BLOCKED_AUTH`, `SOURCE_DELAYED`, `OPTIONAL_BLOCKED`, and `DISABLED`.

## Credential Policy

Do not commit real credential files. Earth Engine, CDS, and Earthdata credentials must remain user-local or environment-provided.

## Processing Stages

1. Build a Sentinel-2 image index with RGB, NIR, NDVI, cloud metadata, and source trace.
2. Build hourly environmental features from ERA5-Land, CHIRPS, SMAP, and optional Open-Meteo cross-checks.
3. Align multimodal samples using Sentinel-2 timestamp `t0` as the anchor.
4. Generate traceable proxy stress labels in the `[0, 1]` range.
5. Create spatiotemporal splits that avoid zone-time leakage.
6. Package artifacts with checksums and validate the dataset contract.

## Phase 1 Boundary

Processing stops after dataset validation and versioning. Model training is out of scope for this phase.

The repository currently contains realtime-ready metadata and tests for registry/schema validation. Real data collection must wait for explicit approval and credential preflight.
