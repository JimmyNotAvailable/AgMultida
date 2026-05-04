# Source Quality Report — GEE-Free Real Download
**Generated:** 2026-05-04T16:43:28+07:00 (UTC: 2026-05-04T09:43:28Z)

## Executive Summary
All 3 required GEE-free sources returned **PASS**. Data quality is sufficient to proceed to the Data Processing/Alignment phase.

---

## Source: Sentinel-2 STAC (P0 Required)

| Metric | Value |
|---|---|
| **Status** | ✅ PASS |
| **Provider** | AWS Earth Search (primary) |
| **STAC URL** | `https://earth-search.aws.element84.com/v1` |
| **Collection** | `sentinel-2-c1-l2a` |
| **Scenes Found** | 13 |
| **Zones Covered** | 6/6 (A01, A02, A03, D01, E01, F01) |
| **Latest Available Date** | 2026-04-29 |
| **Bands Indexed** | B02, B03, B04, B08, SCL |
| **Asset Accessibility** | Verified via HTTP HEAD (200 OK, COG format) |
| **Cloud Cover Filter** | < 50% |

**Quality Notes:**
- Scene catalog and CSV index written to `data/raw/sentinel2/`
- Asset HREFs point to Cloud-Optimized GeoTIFFs on S3 (public, no auth required)
- 5-day gap between latest scene (Apr 29) and today (May 4) — normal for Sentinel-2 processing pipeline
- No fallback to Microsoft Planetary Computer was needed

---

## Source: CHIRPS Direct (P0 Required)

| Metric | Value |
|---|---|
| **Status** | ✅ PASS |
| **Provider** | Climate Hazards Center direct HTTP |
| **Base URL** | `https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05` |
| **Files Downloaded** | 11 daily GeoTIFFs |
| **Total Size** | ~38.5 MB |
| **Date Range** | 2026-03-21 to 2026-03-31 |
| **Latest Available Date** | 2026-03-31 |
| **Production Lag** | ~34 days (normal; CHIRPS daily has ~3-5 week lag) |
| **Coverage** | Global (0.05° resolution) |

**Quality Notes:**
- All 11 files are non-empty compressed GeoTIFFs (3.2–3.9 MB each)
- 34 dates in Apr 2026 returned 404 — this is expected CHIRPS production lag
- SHA-256 checksums computed and stored in manifest
- Data quality is production-grade (same as used in published climate research)

---

## Source: Open-Meteo (P0 Required)

| Metric | Value |
|---|---|
| **Status** | ✅ PASS |
| **Provider** | Open-Meteo Forecast API (`past_days=14`) |
| **Endpoint** | `https://api.open-meteo.com/v1/forecast` |
| **Zones Queried** | 6/6 PASS |
| **Date Range** | 2026-04-20 to 2026-05-04 |
| **Variables** | 12 daily aggregated variables |
| **Output Format** | JSON + CSV per zone + combined CSV |

**Variables Downloaded:**
`temperature_2m_max`, `temperature_2m_min`, `temperature_2m_mean`, `relative_humidity_2m_max`, `relative_humidity_2m_min`, `dew_point_2m_min`, `dew_point_2m_max`, `precipitation_sum`, `rain_sum`, `wind_speed_10m_max`, `shortwave_radiation_sum`, `et0_fao_evapotranspiration`

**Quality Notes:**
- Archive API returned HTTP 400 for dates extending into May 2026 (data not yet available in archive)
- Successfully fell through to Forecast API with `past_days=14` which returned complete data
- All 6 zones have 14-15 rows of daily weather data with no null values for core variables
- ET₀ FAO evapotranspiration included — critical for water stress proxy label computation

---

## Disabled/Blocked Sources (Not Required for GEE-Free Path)

| Source | Status | Reason |
|---|---|---|
| sentinel2_gee | DISABLED | GEE project billing blocked |
| chirps_gee | DISABLED | GEE project billing blocked |
| era5_land | OPTIONAL_BLOCKED | CDS auth required (optional preferred) |
| smap | OPTIONAL_BLOCKED | NASA Earthdata auth required (optional) |
