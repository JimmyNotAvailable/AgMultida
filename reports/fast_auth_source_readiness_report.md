# Fast Auth And Minimum Real Download Readiness

Generated UTC: 2026-05-04T08:09:18.663793+00:00

## Executive Verdict

STILL_BLOCKED_GEE_AUTH

## GEE Auth Status

- Credential file presence check: GEE_MISSING
- `ee.Initialize()` status: ERROR_REQUIRES_AUTHENTICATE
- Credential values were not read or printed.

## Fast Auth Status

- Google Earth Engine: MISSING
- Copernicus CDS: MISSING (`~/.cdsapirc` not present)
- Earthdata: MISSING (`EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` not present)
- Open-Meteo: READY, no auth required

## Required Sources Ready

- open_meteo

## Required Sources Blocked

- sentinel2: BLOCKED_AUTH because Google Earth Engine auth is missing.
- chirps: BLOCKED_AUTH because Google Earth Engine auth is missing.

## Optional Sources Ready

- none

## Optional Sources Blocked

- era5_land: OPTIONAL_BLOCKED because CDS `~/.cdsapirc` is missing.
- smap: OPTIONAL_BLOCKED because Earthdata env vars are missing.

## Dry-run Evidence

- `python3 scripts/run_data_collection.py --dry-run`: PASS, 5 sources checked, `writes_primary_data=false`
- `python3 -m pytest tests/data_pipeline -q`: PASS, 19 passed
- secret scan: PASS

## GEE Auth Command

Run on the VPS:

```bash
earthengine authenticate --auth_mode=gcloud
```

Alternative browser/code flow:

```bash
earthengine authenticate --quiet
```

Then verify presence only:

```bash
test -f ~/.config/earthengine/credentials && echo GEE_READY || echo GEE_MISSING
```

## Exact Real Download Plan

Blocked until GEE is ready. Once GEE is ready, the minimum viable real download plan is:

1. Sentinel-2 from GEE
2. CHIRPS from GEE
3. Open-Meteo Archive API

ERA5-Land and SMAP remain optional and should not block the minimum run.

## Awaiting Approval

Real download still requires exact approval after GEE is ready:

`APPROVE DATA REAL DOWNLOAD`
