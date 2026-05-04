"""Validate dataset samples against data_contract.yaml.

CLI script to verify that serialized samples conform to the
aligned_multimodal_sample contract. Reports all violations
with descriptive messages.

Usage:
    python scripts/validate_dataset_contract.py --sample path/to/sample.json
    python scripts/validate_dataset_contract.py --dry-run

Exit codes:
    0 = all samples valid
    1 = validation errors found
    2 = file not found or parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml_pipeline.data.sample import AlignedSample


def _make_dry_run_sample() -> AlignedSample:
    """Create a contract-compliant sample for dry-run validation."""
    torch.manual_seed(42)
    return AlignedSample(
        sample_id="A01_20240214_S2",
        zone_id="A01",
        timestamp=datetime(2024, 2, 14, 3, 21, 0, tzinfo=timezone.utc),
        image=torch.rand(4, 224, 224),
        sensor_seq=torch.rand(48, 8),
        weather_ctx=torch.rand(6),
        modality_mask=torch.tensor([1.0, 1.0, 1.0]),
        label=0.42,
        source_trace={
            "image_source": "sentinel2_L2A",
            "sensor_sources": ["era5_land", "smap"],
            "weather_source": "open_meteo",
            "label_formula": "ndvi_delta_threshold",
            "alignment_method": "nearest_temporal",
            "cloud_rate": 0.05,
        },
    )


def _load_sample_from_json(path: Path) -> AlignedSample:
    """Load a sample from JSON metadata + tensor files.

    Expected JSON structure:
        {
            "sample_id": "A01_20240214_S2",
            "zone_id": "A01",
            "timestamp": "2024-02-14T03:21:00Z",
            "tensor_dir": "./tensors/",
            "label": 0.42,
            "source_trace": {...}
        }

    Tensor files expected in tensor_dir:
        image.pt, sensor_seq.pt, weather_ctx.pt, modality_mask.pt
    """
    with open(path) as f:
        meta = json.load(f)

    tensor_dir = path.parent / meta.get("tensor_dir", ".")

    return AlignedSample(
        sample_id=meta["sample_id"],
        zone_id=meta["zone_id"],
        timestamp=datetime.fromisoformat(meta["timestamp"]),
        image=torch.load(tensor_dir / "image.pt", weights_only=True),
        sensor_seq=torch.load(tensor_dir / "sensor_seq.pt", weights_only=True),
        weather_ctx=torch.load(tensor_dir / "weather_ctx.pt", weights_only=True),
        modality_mask=torch.load(tensor_dir / "modality_mask.pt", weights_only=True),
        label=float(meta["label"]),
        source_trace=meta["source_trace"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate dataset samples against data_contract.yaml",
    )
    parser.add_argument(
        "--sample", type=Path,
        help="Path to a sample JSON metadata file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate a synthetic sample (no files needed)",
    )
    args = parser.parse_args()

    if args.dry_run:
        try:
            sample = _make_dry_run_sample()
            print(f"Dry-run sample '{sample.sample_id}' PASSED contract validation")
            return 0
        except ValueError as e:
            print(f"Dry-run FAILED: {e}", file=sys.stderr)
            return 1

    if not args.sample:
        parser.error("Provide --sample or --dry-run")

    if not args.sample.exists():
        print(f"File not found: {args.sample}", file=sys.stderr)
        return 2

    try:
        sample = _load_sample_from_json(args.sample)
        print(f"Sample '{sample.sample_id}' PASSED contract validation")
        return 0
    except (ValueError, KeyError, FileNotFoundError) as e:
        print(f"Validation FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
