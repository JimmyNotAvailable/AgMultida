"""Config builders and data loaders for training pipeline."""
from __future__ import annotations

import ast
import hashlib
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from torch.amp import GradScaler
from torch.utils.data import DataLoader, Dataset

from ml_pipeline.data.sample import EXPECTED_SHAPES
from ml_pipeline.models.network import MultimodalStressNet
from ml_pipeline.training.losses import ProxyRegressionLoss

REQUIRED_MANIFEST_COLUMNS = {
    "sample_id",
    "zone_id",
    "image_path",
    "sensor_seq_path",
    "weather_ctx_path",
    "modality_mask",
    "label",
    "source_status",
}
ALLOWED_SOURCE_STATUS = {"PASS"}


class ManifestDataset(Dataset):
    """Load training samples from manifest rows with local relative .npy paths."""

    def __init__(self, manifest_path: str | Path, validate_checksums: bool = False) -> None:
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        self.root_dir = self.manifest_path.parent
        frame = pd.read_csv(self.manifest_path)
        missing = REQUIRED_MANIFEST_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(f"Manifest missing required columns {sorted(missing)}: {self.manifest_path}")
        self.rows = frame.to_dict("records")
        if not self.rows:
            raise ValueError(f"Manifest has no rows: {self.manifest_path}")
        for index, row in enumerate(self.rows):
            self._validate_row(index, row, validate_checksums)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        row = self.rows[idx]
        sample_id = str(row["sample_id"])
        image = self._load_tensor(idx, sample_id, row["image_path"], "image", EXPECTED_SHAPES["image"])
        sensor_seq = self._load_tensor(idx, sample_id, row["sensor_seq_path"], "sensor_seq", EXPECTED_SHAPES["sensor_seq"])
        weather_ctx = self._load_tensor(idx, sample_id, row["weather_ctx_path"], "weather_ctx", EXPECTED_SHAPES["weather_ctx"])
        modality_mask = self._parse_mask(idx, sample_id, row["modality_mask"])
        label = self._parse_label(idx, sample_id, row["label"])
        return {
            "image": image,
            "sensor_seq": sensor_seq,
            "weather_ctx": weather_ctx,
            "modality_mask": modality_mask,
            "label": torch.tensor([label], dtype=torch.float32),
        }

    def _validate_row(self, idx: int, row: dict[str, Any], validate_checksums: bool) -> None:
        sample_id = str(row["sample_id"])
        source_status = str(row["source_status"])
        if source_status not in ALLOWED_SOURCE_STATUS:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} has unsupported source_status {source_status!r}; "
                f"expected one of {sorted(ALLOWED_SOURCE_STATUS)}"
            )
        self._parse_label(idx, sample_id, row["label"])
        self._parse_mask(idx, sample_id, row["modality_mask"])
        image_path = self._resolve_path(row["image_path"])
        sensor_path = self._resolve_path(row["sensor_seq_path"])
        weather_path = self._resolve_path(row["weather_ctx_path"])
        if validate_checksums:
            checksum_pairs = [
                ("image_checksum", image_path, "image"),
                ("sensor_seq_checksum", sensor_path, "sensor_seq"),
                ("weather_ctx_checksum", weather_path, "weather_ctx"),
            ]
            if all(column in row for column, _, _ in checksum_pairs):
                for column, path, field_name in checksum_pairs:
                    checksum = str(row[column])
                    if checksum and self._sha256_file(path) != checksum:
                        raise ValueError(
                            f"Manifest row {idx} sample_id={sample_id} checksum mismatch for {field_name} tensor"
                        )
            elif "checksum" in row:
                checksum = str(row["checksum"])
                if checksum and self._sha256_file(image_path) != checksum:
                    raise ValueError(
                        f"Manifest row {idx} sample_id={sample_id} checksum mismatch for image tensor"
                    )
        self._validate_tensor(idx, sample_id, image_path, "image", EXPECTED_SHAPES["image"])
        self._validate_tensor(idx, sample_id, sensor_path, "sensor_seq", EXPECTED_SHAPES["sensor_seq"])
        self._validate_tensor(idx, sample_id, weather_path, "weather_ctx", EXPECTED_SHAPES["weather_ctx"])

    def _validate_tensor(
        self,
        idx: int,
        sample_id: str,
        path: Path,
        field_name: str,
        expected_shape: tuple[int, ...],
    ) -> None:
        arr = np.load(path)
        if arr.shape != expected_shape:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} field={field_name} shape {arr.shape} != {expected_shape}"
            )
        if arr.dtype != np.float32:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} field={field_name} dtype {arr.dtype} != float32"
            )

    def _load_tensor(
        self,
        idx: int,
        sample_id: str,
        path_value: str,
        field_name: str,
        expected_shape: tuple[int, ...],
    ) -> torch.Tensor:
        path = self._resolve_path(path_value)
        arr = np.load(path)
        if arr.shape != expected_shape:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} field={field_name} shape {arr.shape} != {expected_shape}"
            )
        if arr.dtype != np.float32:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} field={field_name} dtype {arr.dtype} != float32"
            )
        return torch.from_numpy(arr).to(torch.float32)

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute() and path.exists():
            return path
        normalized = path_value.replace("\\", "/")
        if "/samples/" in normalized:
            suffix = normalized.split("/samples/", 1)[1]
            candidate = self.root_dir / "samples" / suffix
            if candidate.exists():
                return candidate
        candidate = self.root_dir / path_value
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Could not resolve sample path: {path_value}")

    def _parse_mask(self, idx: int, sample_id: str, value: Any) -> torch.Tensor:
        try:
            parsed = ast.literal_eval(str(value))
        except (ValueError, SyntaxError) as error:
            raise ValueError(f"Manifest row {idx} sample_id={sample_id} has invalid modality_mask: {value!r}") from error
        mask = torch.tensor(parsed, dtype=torch.float32)
        if tuple(mask.shape) != EXPECTED_SHAPES["modality_mask"]:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} modality_mask shape {tuple(mask.shape)} != {EXPECTED_SHAPES['modality_mask']}"
            )
        unique = set(mask.tolist())
        if not unique.issubset({0.0, 1.0}):
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} modality_mask must contain only 0.0 or 1.0"
            )
        if float(mask.sum().item()) < 1.0:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} modality_mask must keep at least one modality"
            )
        return mask

    def _parse_label(self, idx: int, sample_id: str, value: Any) -> float:
        label = float(value)
        if not 0.0 <= label <= 1.0:
            raise ValueError(
                f"Manifest row {idx} sample_id={sample_id} label {label} is outside [0.0, 1.0]"
            )
        return label

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain mapping at root: {path}")
    return payload


def resolve_device(device_str: str) -> torch.device:
    if device_str == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_str)


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def build_model(config: dict[str, Any], pretrained: bool | None = None) -> MultimodalStressNet:
    image_cfg = config["image_encoder"]
    fusion_cfg = config["fusion"]
    temp_cfg = config["temporal_encoder"]
    wth_cfg = config["weather_encoder"]
    reg_cfg = config["regularization"]

    use_pretrained = pretrained if pretrained is not None else (image_cfg.get("pretrained") == "imagenet")

    return MultimodalStressNet(
        d_model=fusion_cfg["d_model"],
        num_heads=fusion_cfg["num_heads"],
        sensor_input_dim=temp_cfg["input_dim"],
        sensor_hidden_dim=temp_cfg["hidden_dim"],
        sensor_num_layers=temp_cfg["num_layers"],
        sensor_dropout=temp_cfg["dropout"],
        weather_input_dim=wth_cfg["input_dim"],
        weather_hidden_dim=wth_cfg["hidden_dim"],
        modality_dropout_p=reg_cfg["modality_dropout"],
        fusion_dropout=fusion_cfg["dropout"],
        pretrained_backbone=use_pretrained,
    )


def build_loss(config: dict[str, Any]) -> nn.Module:
    train_cfg = config["training"]
    reg_cfg = config["regularization"]
    if train_cfg["loss"] != "proxy_mse":
        raise ValueError(f"Unsupported loss: {train_cfg['loss']}")
    return ProxyRegressionLoss(
        smoothing=reg_cfg["label_smoothing"],
    )


def build_optimizer(model: nn.Module, config: dict[str, Any]) -> torch.optim.Optimizer:
    train_cfg = config["training"]
    if train_cfg["optimizer"] != "adamw":
        raise ValueError(f"Unsupported optimizer: {train_cfg['optimizer']}")
    return torch.optim.AdamW(
        model.parameters(),
        lr=float(train_cfg["lr"]),
        weight_decay=float(train_cfg["weight_decay"]),
    )


def build_scheduler(
    optimizer: torch.optim.Optimizer,
    config: dict[str, Any],
    steps_per_epoch: int,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    train_cfg = config["training"]
    sched_type = train_cfg.get("scheduler", "none")
    if sched_type == "none":
        return None
    if sched_type == "one_cycle_lr":
        return torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=float(train_cfg["lr"]),
            epochs=int(train_cfg["max_epochs"]),
            steps_per_epoch=max(1, steps_per_epoch),
            pct_start=float(train_cfg.get("scheduler_pct_start", 0.1)),
        )
    raise ValueError(f"Unsupported scheduler: {sched_type}")


def build_scaler(device: torch.device, amp_enabled: bool) -> GradScaler:
    return GradScaler(enabled=(amp_enabled and device.type == "cuda"))


def build_dataloader(
    manifest_path: str | Path,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
    pin_memory: bool,
    prefetch_factor: int,
    persistent_workers: bool,
    validate_checksums: bool = False,
) -> DataLoader:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    dataset = ManifestDataset(manifest_path, validate_checksums=validate_checksums)
    use_workers = max(0, num_workers)
    kwargs: dict[str, Any] = {
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": use_workers,
        "pin_memory": pin_memory,
    }
    if use_workers > 0:
        kwargs["prefetch_factor"] = prefetch_factor
        kwargs["persistent_workers"] = persistent_workers
    return DataLoader(dataset, **kwargs)
