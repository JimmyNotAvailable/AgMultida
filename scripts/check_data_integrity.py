#!/usr/bin/env python3
"""Data integrity checker for AgMultida pipeline.

Verifies that all files referenced in a manifest exist, are non-empty,
and load successfully as numpy arrays with expected shapes and dtypes.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EXPECTED_SHAPES = {
    "image_path": (4, 224, 224),
    "sensor_seq_path": (48, 8),
    "weather_ctx_path": (6,),
}

def verify_dataset(data_dir: str | Path) -> dict[str, object]:
    root = Path(data_dir)
    manifest_path = root / "sample_manifest.csv"

    if not manifest_path.exists():
        logging.error(f"Manifest not found: {manifest_path}")
        return {"status": "FAIL", "reason": "manifest_missing"}

    df = pd.read_csv(manifest_path)
    if "stress_label" in df.columns and "label" not in df.columns:
        df = df.rename(columns={"stress_label": "label"})

    report = {
        "status": "PASS",
        "total_samples": len(df),
        "total_arrays": len(df) * 3,
        "valid_arrays": 0,
        "missing_files": 0,
        "empty_files": 0,
        "load_errors": 0,
        "shape_errors": 0,
        "mask_errors": 0,
        "errors": []
    }

    for _, row in df.iterrows():
        sample_id = row["sample_id"]

        # Verify mask
        mask_val = row.get("modality_mask")
        if mask_val:
            try:
                mask = ast.literal_eval(str(mask_val))
                if len(mask) != 3 or sum(mask) < 1.0 or any(x not in (0.0, 1.0) for x in mask):
                    report["mask_errors"] += 1
                    report["errors"].append(f"{sample_id}: Invalid mask {mask}")
            except Exception as e:
                report["mask_errors"] += 1
                report["errors"].append(f"{sample_id}: Mask parse error {e}")

        # Verify tensors
        for col, expected_shape in EXPECTED_SHAPES.items():
            path_val = str(row[col])
            # Resolve path relative to manifest if it's relative
            p = Path(path_val)
            if not p.is_absolute():
                # If path contains 'samples/', try to resolve relative to root
                norm = path_val.replace("\\", "/")
                if "samples/" in norm:
                    suffix = norm.split("samples/", 1)[1]
                    p = root / "samples" / suffix
                else:
                    p = root / p

            if not p.exists():
                report["missing_files"] += 1
                if len(report["errors"]) < 10:
                    report["errors"].append(f"{sample_id}: Missing {col} -> {p}")
                continue

            if p.stat().st_size == 0:
                report["empty_files"] += 1
                if len(report["errors"]) < 10:
                    report["errors"].append(f"{sample_id}: Empty {col} -> {p}")
                continue

            try:
                arr = np.load(p)
                if arr.shape != expected_shape:
                    report["shape_errors"] += 1
                    if len(report["errors"]) < 10:
                        report["errors"].append(f"{sample_id}: Shape mismatch {col} {arr.shape} != {expected_shape}")
                elif arr.dtype != np.float32:
                    report["shape_errors"] += 1
                    if len(report["errors"]) < 10:
                        report["errors"].append(f"{sample_id}: Dtype mismatch {col} {arr.dtype} != float32")
                else:
                    report["valid_arrays"] += 1
            except Exception as e:
                report["load_errors"] += 1
                if len(report["errors"]) < 10:
                    report["errors"].append(f"{sample_id}: Load error {col} -> {type(e).__name__}")

    if report["valid_arrays"] < report["total_arrays"] or report["mask_errors"] > 0:
        report["status"] = "FAIL"

    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/aligned/v1_water_stress", help="Path to aligned dataset dir")
    args = parser.parse_args()

    report = verify_dataset(args.data_dir)
    print(json.dumps(report, indent=2))

    if report["status"] == "FAIL":
        exit(1)

if __name__ == "__main__":
    main()
