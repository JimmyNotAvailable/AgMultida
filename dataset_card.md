# Dataset Card: Water Stress Phase 1

## Dataset Name

AgMultida Water Stress Proxy Dataset (`data/processed_real`)

## Intended Use

Pipeline validation and first-pass training for rice water-stress detection and water-saving irrigation recommendation.

## Status

- Canonical training root: `data/processed_real/`
- Final manifest: `data/processed_real/sample_manifest.csv`
- Historical expansion is expected to change sample counts over time.
- Labels: continuous proxy stress label `[0, 1]`
- Primary training metrics should be continuous (`loss`, `mae`, `rmse`); binary metrics are diagnostics only.

## Modalities

- Sentinel-2 RGB+NIR image patch: `[4, 224, 224]`
- Weather-derived sensor sequence: `[48, 8]`
- Weather context: `[6]`
- Modality mask: `[3]`
- Label: `[1]`

## Label Formula and Limitations

Labels are proxy labels based on NDVI anomaly, ET deficit, rain relief, and heat penalty. They are not field-measured stress labels and should not be presented as agronomist-verified ground truth.

## Sensor Limitation

`sensor_seq` is weather-derived proxy data, not telemetry from physical field devices. It is appropriate for Phase 1 pipeline validation but not for claims about field-sensor performance.

## Geometry Limitation

Zones are synthetic validation polygons, not audited farm boundaries.

## Training Claim Boundary

Safe claim: multimodal proxy-label regression pipeline for water-stress scoring and irrigation recommendation.

Unsafe claims:

- field-ready agronomic accuracy
- rice blast detection
- brown planthopper detection
- nitrogen deficiency detection
- physical sensor telemetry validation

## Current Data Integrity Warning

The manifests and `.npy` tensors must pass integrity checks before full training. Manifest loader now expects `source_status == PASS` and can optionally validate checksums. Run `scripts/check_data_integrity.py --data-dir data/processed_real` before VPS launch.
