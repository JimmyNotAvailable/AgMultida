# Realtime Readiness Report

## Executive Verdict

METADATA_REALTIME_READY

## Timezone Policy

- Local scheduling timezone: Asia/Ho_Chi_Minh
- Storage/query/log timezone: UTC
- Timestamp format: ISO-8601 UTC
- Naive datetime allowed: false

## Realtime Incremental Mode

- Enabled: true
- Run at local time: 06:00
- Lookback days: 14
- Latest available policy: search backward within the lookback window if local today is unavailable.

## Source Status Policy

Allowed statuses:

- PASS
- WARN
- FAIL
- BLOCKED_AUTH
- SOURCE_DELAYED
- OPTIONAL_BLOCKED

Delayed or auth-blocked sources must not be marked as PASS.

## Remaining Blockers

- Google Earth Engine auth missing for Sentinel-2 and CHIRPS.
- CDS `~/.cdsapirc` missing for optional preferred ERA5-Land.
- Earthdata env vars missing for optional SMAP path.

Real download still requires exact approval: `APPROVE DATA REAL DOWNLOAD`.
