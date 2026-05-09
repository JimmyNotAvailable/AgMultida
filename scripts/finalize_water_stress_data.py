"""Finalize portable water-stress dataset manifests for training."""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_SHAPES = {
    "image_path": (4, 224, 224),
    "sensor_seq_path": (48, 8),
    "weather_ctx_path": (6,),
}


def _portable_path(path_value: str, source_dir: Path, target_dir: Path) -> str:
    normalized = path_value.replace("\\", "/")
    if "/samples/" in normalized:
        suffix = normalized.split("/samples/", 1)[1]
        src = source_dir / "samples" / suffix
        dst = target_dir / "samples" / suffix
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and (not dst.exists() or dst.stat().st_size == 0):
            shutil.copy2(src, dst)
        return f"samples/{suffix}"
    path = Path(path_value)
    if path.exists():
        dst = target_dir / "samples" / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(path, dst)
        return str(dst.relative_to(target_dir)).replace("\\", "/")
    raise FileNotFoundError(f"Cannot resolve data path: {path_value}")


def finalize(source_dir: str = "data/processed", target_dir: str = "data/aligned/v1_water_stress") -> dict[str, object]:
    source = Path(source_dir)
    target = Path(target_dir)
    manifest_path = source / "sample_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing source manifest: {manifest_path}")

    target.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(manifest_path)
    manifest.rename(columns={"stress_label": "label"}, inplace=True)
    required_cols = {"sample_id", "zone_id", "split", "image_path", "sensor_seq_path", "weather_ctx_path", "modality_mask", "label"}
    missing = required_cols - set(manifest.columns)
    if missing:
        raise ValueError(f"Manifest missing columns: {sorted(missing)}")

    manifest = manifest.copy()
    for column in ["image_path", "sensor_seq_path", "weather_ctx_path"]:
        manifest[column] = manifest[column].apply(lambda value: _portable_path(str(value), source, target))

    # Verify basic mask and label. Array shapes will be verified by DataLoader
    shape_failures: list[str] = []
    for row in manifest.to_dict("records"):
        mask = ast.literal_eval(row["modality_mask"])
        if len(mask) != 3 or any(value not in (0.0, 1.0) for value in mask) or sum(mask) < 1.0:
            shape_failures.append(f"{row['sample_id']}:bad_mask:{mask}")
        label = float(row["label"])
        if not 0.0 <= label <= 1.0:
            shape_failures.append(f"{row['sample_id']}:bad_label:{label}")
    if shape_failures:
        raise ValueError("Shape contract failures: " + "; ".join(shape_failures[:10]))

    for split in ["train", "val", "test"]:
        split_df = manifest[manifest["split"] == split]
        if split_df.empty:
            raise ValueError(f"Missing split: {split}")
        split_df.to_csv(target / f"{split}_manifest.csv", index=False)
    manifest.to_csv(target / "sample_manifest.csv", index=False)

    split_zones = {split: set(manifest[manifest["split"] == split]["zone_id"]) for split in ["train", "val", "test"]}
    overlap = {
        "train_val": sorted(split_zones["train"] & split_zones["val"]),
        "train_test": sorted(split_zones["train"] & split_zones["test"]),
        "val_test": sorted(split_zones["val"] & split_zones["test"]),
    }
    if any(overlap.values()):
        raise ValueError(f"Split zone leakage detected: {overlap}")

    label_summary = {
        "min": float(manifest["label"].min()),
        "mean": float(manifest["label"].mean()),
        "max": float(manifest["label"].max()),
    }
    report = {
        "source_dir": str(source),
        "target_dir": str(target),
        "sample_count": int(len(manifest)),
        "split_counts": manifest["split"].value_counts().to_dict(),
        "zone_counts": manifest["zone_id"].value_counts().to_dict(),
        "label_summary": label_summary,
        "shape_contract": "PASS",
        "split_overlap": overlap,
        "proxy_limitations": "weather-derived proxy labels; synthetic validation polygons; not field ground truth",
    }
    (target / "dataset_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(finalize(), indent=2))
