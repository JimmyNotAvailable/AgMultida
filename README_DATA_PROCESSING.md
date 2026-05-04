# Data Processing Runbook

This scaffold defines the intended processing stages before model training.

## Stages

1. Build a Sentinel-2 image index with RGB, NIR, NDVI, cloud metadata, and source trace.
2. Build hourly environmental features from ERA5-Land, CHIRPS, SMAP, and optional Open-Meteo cross-checks.
3. Align multimodal samples using Sentinel-2 timestamp `t0` as the anchor.
4. Generate traceable proxy stress labels in the `[0, 1]` range.
5. Create spatiotemporal splits that avoid zone-time leakage.
6. Package artifacts with checksums and validate the dataset contract.

## No Training Boundary

Processing stops after dataset validation and versioning. Model training is out of scope for this phase.
