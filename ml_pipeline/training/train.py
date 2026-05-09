"""Training loop and checkpoint management for MultimodalStressNet."""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader

from ml_pipeline.training.metrics import BinaryMetrics, ContinuousMetrics
from ml_pipeline.training.builders import (
    build_dataloader,
    build_loss,
    build_model,
    build_optimizer,
    build_scaler,
    build_scheduler,
    load_yaml,
    resolve_device,
    set_global_seed,
)

logger = logging.getLogger(__name__)

METRIC_FIELDS = [
    "epoch",
    "train_loss",
    "train_grad_norm",
    "val_loss",
    "val_mae",
    "val_rmse",
    "val_binary_f1",
    "val_binary_auc_roc",
    "lr",
    "test_loss",
    "test_mae",
    "test_rmse",
    "test_binary_f1",
    "test_binary_auc_roc",
]


def train_one_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler],
    scaler: GradScaler,
    device: torch.device,
) -> dict[str, float]:
    model.train()
    total_loss = 0.0
    total_grad_norm = 0.0
    num_batches = len(dataloader)
    device_type = "cuda" if device.type == "cuda" else "cpu"
    amp_enabled = scaler.is_enabled()

    for batch_idx, batch in enumerate(dataloader):
        inputs = {k: v.to(device, non_blocking=True) for k, v in batch.items() if k != "label"}
        labels = batch["label"].to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with autocast(device_type=device_type, enabled=amp_enabled):
            logits, _ = model(**inputs)
            loss = loss_fn(logits, labels)

        if not torch.isfinite(loss):
            raise ValueError(f"Non-finite loss detected at batch {batch_idx}: {loss.item()}")

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        if not torch.isfinite(grad_norm):
            raise ValueError(f"Non-finite grad norm detected at batch {batch_idx}: {grad_norm.item()}")
        scaler.step(optimizer)
        scaler.update()

        if scheduler is not None:
            scheduler.step()

        total_loss += loss.item()
        total_grad_norm += float(grad_norm.item())

    return {
        "loss": total_loss / max(1, num_batches),
        "grad_norm": total_grad_norm / max(1, num_batches),
    }


@torch.no_grad()
def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    loss_fn: nn.Module,
    metrics: ContinuousMetrics,
    device: torch.device,
    binary_metrics: BinaryMetrics | None = None,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    num_batches = len(dataloader)
    metrics.reset()
    if binary_metrics is not None:
        binary_metrics.reset()

    for batch in dataloader:
        inputs = {k: v.to(device, non_blocking=True) for k, v in batch.items() if k != "label"}
        labels = batch["label"].to(device, non_blocking=True)
        logits, _ = model(**inputs)
        loss = loss_fn(logits, labels)
        if not torch.isfinite(loss):
            raise ValueError(f"Non-finite eval loss detected: {loss.item()}")
        total_loss += loss.item()
        metrics.update(logits, labels)
        if binary_metrics is not None:
            binary_metrics.update(logits, labels)

    results = metrics.compute()
    if binary_metrics is not None:
        results.update(binary_metrics.compute())
    results["loss"] = total_loss / max(1, num_batches)
    return results


def save_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler],
    epoch: int,
    metrics: dict[str, float],
    model_version: str = "1.0.0",
    config: Optional[dict[str, Any]] = None,
    scaler: Optional[GradScaler] = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    state = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
        "scaler_state_dict": scaler.state_dict() if scaler else None,
        "metrics": metrics,
        "model_version": model_version,
        "config": config or {},
    }
    torch.save(state, tmp_path)
    tmp_path.replace(path)
    logger.info("Saved checkpoint to %s", path)


def load_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    device: Optional[torch.device] = None,
    scaler: Optional[GradScaler] = None,
) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    state = torch.load(path, map_location=device, weights_only=False)
    model.load_state_dict(state["model_state_dict"])
    if optimizer is not None and state.get("optimizer_state_dict"):
        optimizer.load_state_dict(state["optimizer_state_dict"])
    if scheduler is not None and state.get("scheduler_state_dict"):
        scheduler.load_state_dict(state["scheduler_state_dict"])
    if scaler is not None and state.get("scaler_state_dict"):
        scaler.load_state_dict(state["scaler_state_dict"])
    logger.info("Loaded checkpoint from %s (epoch %s)", path, state.get("epoch"))
    return {
        "epoch": state.get("epoch", 0),
        "metrics": state.get("metrics", {}),
        "model_version": state.get("model_version", "unknown"),
        "config": state.get("config", {}),
    }


def _merge_config(config_dir: str | Path) -> dict[str, Any]:
    config_dir = Path(config_dir)
    model_config = load_yaml(config_dir / "model.yaml")
    train_config = load_yaml(config_dir / "train.yaml")
    full_config = {**model_config, "training": train_config.get("training", {})}
    if "training" in model_config:
        full_config["training"] = {**model_config["training"], **train_config.get("training", {})}
    return full_config


def _write_metrics(log_path: Path, row: dict[str, float | int | str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    exists = log_path.exists()
    normalized_row = {field: row.get(field, "") for field in METRIC_FIELDS}
    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(normalized_row)


def _make_mock_dataloader(batch_size: int, num_samples: int) -> DataLoader:
    samples = []
    for _ in range(num_samples):
        samples.append({
            "image": torch.randn(4, 224, 224),
            "sensor_seq": torch.randn(48, 8),
            "weather_ctx": torch.randn(6),
            "modality_mask": torch.ones(3),
            "label": torch.rand(1),
        })

    class MockDataset(torch.utils.data.Dataset):
        def __len__(self):
            return len(samples)
        def __getitem__(self, idx):
            return samples[idx]

    return DataLoader(MockDataset(), batch_size=batch_size)


def main(
    config_dir: str | Path = "ml_pipeline/configs",
    data_dir: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
    log_dir: str | Path | None = None,
    dry_run: bool = False,
    resume: str | Path | None = None,
    amp: bool | None = None,
    seed: int | None = None,
    num_workers: int | None = None,
    max_epochs: int | None = None,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    full_config = _merge_config(config_dir)
    train_cfg = full_config["training"]

    if seed is not None:
        train_cfg["seed"] = seed
    set_global_seed(int(train_cfg.get("seed", 42)))

    if amp is not None:
        train_cfg["amp"] = amp
    if max_epochs is not None:
        train_cfg["max_epochs"] = max_epochs
    if checkpoint_dir is not None:
        train_cfg["checkpoint_dir"] = str(checkpoint_dir)

    device = resolve_device(train_cfg.get("device", "auto"))
    logger.info("Using device: %s", device)

    is_dry_run = dry_run or bool(train_cfg.get("dry_run", False))
    model = build_model(full_config, pretrained=False if is_dry_run else None).to(device)
    loss_fn = build_loss(full_config).to(device)
    optimizer = build_optimizer(model, full_config)

    batch_size = int(train_cfg.get("batch_size", 32))
    loader_workers = int(num_workers if num_workers is not None else train_cfg.get("num_workers", 4))
    pin_memory = device.type == "cuda"
    validate_checksums = bool(train_cfg.get("validate_checksums", False))
    test_loader: DataLoader | None = None

    if is_dry_run:
        train_loader = _make_mock_dataloader(batch_size, num_samples=batch_size * 2)
        val_loader = _make_mock_dataloader(batch_size, num_samples=batch_size)
        train_cfg["max_epochs"] = min(int(train_cfg.get("max_epochs", 2)), 2)
    else:
        root = Path(data_dir or train_cfg["data_dir"])
        train_loader = build_dataloader(
            root / "train_manifest.csv",
            batch_size=batch_size,
            shuffle=True,
            num_workers=loader_workers,
            pin_memory=pin_memory,
            prefetch_factor=int(train_cfg.get("prefetch_factor", 2)),
            persistent_workers=bool(train_cfg.get("persistent_workers", True)),
            validate_checksums=validate_checksums,
        )
        val_loader = build_dataloader(
            root / "val_manifest.csv",
            batch_size=batch_size,
            shuffle=False,
            num_workers=loader_workers,
            pin_memory=pin_memory,
            prefetch_factor=int(train_cfg.get("prefetch_factor", 2)),
            persistent_workers=bool(train_cfg.get("persistent_workers", True)),
            validate_checksums=validate_checksums,
        )
        if bool(train_cfg.get("evaluate_test_manifest", True)):
            test_loader = build_dataloader(
                root / "test_manifest.csv",
                batch_size=batch_size,
                shuffle=False,
                num_workers=loader_workers,
                pin_memory=pin_memory,
                prefetch_factor=int(train_cfg.get("prefetch_factor", 2)),
                persistent_workers=bool(train_cfg.get("persistent_workers", True)),
                validate_checksums=validate_checksums,
            )

    scheduler = build_scheduler(optimizer, full_config, len(train_loader))
    scaler = build_scaler(device, bool(train_cfg.get("amp", False)))
    start_epoch = 1
    if resume:
        metadata = load_checkpoint(resume, model, optimizer, scheduler, device, scaler)
        start_epoch = int(metadata["epoch"]) + 1

    checkpoint_path = Path(train_cfg.get("checkpoint_dir", "checkpoints/"))
    log_path = Path(log_dir or "logs") / "training_metrics.csv"
    continuous_metrics = ContinuousMetrics()
    binary_metrics = BinaryMetrics()
    checkpoint_metric = str(train_cfg.get("checkpoint_metric", "rmse"))
    if checkpoint_metric not in {"rmse", "mae", "loss"}:
        raise ValueError(f"Unsupported checkpoint_metric: {checkpoint_metric}")
    best_score = float("inf")
    patience = int(train_cfg.get("early_stopping_patience", 7))
    patience_counter = 0
    total_epochs = int(train_cfg.get("max_epochs", 50))

    for epoch in range(start_epoch, total_epochs + 1):
        logger.info("--- Epoch %s/%s ---", epoch, total_epochs)
        train_metrics = train_one_epoch(model, train_loader, loss_fn, optimizer, scheduler, scaler, device)
        val_metrics = evaluate(model, val_loader, loss_fn, continuous_metrics, device, binary_metrics)
        score = float(val_metrics[checkpoint_metric])

        row = {
            "epoch": epoch,
            "train_loss": train_metrics["loss"],
            "train_grad_norm": train_metrics["grad_norm"],
            "val_loss": val_metrics["loss"],
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "val_binary_f1": val_metrics.get("binary_f1", float("nan")),
            "val_binary_auc_roc": val_metrics.get("binary_auc_roc", float("nan")),
            "lr": optimizer.param_groups[0]["lr"],
        }
        _write_metrics(log_path, row)
        logger.info("Metrics: %s", row)

        save_checkpoint(
            checkpoint_path / "latest.pt",
            model,
            optimizer,
            scheduler,
            epoch,
            val_metrics,
            model_version=full_config["model"]["version"],
            config=full_config,
            scaler=scaler,
        )
        if score < best_score:
            best_score = score
            patience_counter = 0
            save_checkpoint(
                checkpoint_path / "best.pt",
                model,
                optimizer,
                scheduler,
                epoch,
                val_metrics,
                model_version=full_config["model"]["version"],
                config=full_config,
                scaler=scaler,
            )
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info("Early stopping triggered after %s epochs", epoch)
                break

    if test_loader is not None:
        best_model = build_model(full_config, pretrained=False if is_dry_run else None).to(device)
        load_checkpoint(checkpoint_path / "best.pt", best_model, device=device)
        test_metrics = evaluate(best_model, test_loader, loss_fn, ContinuousMetrics(), device, BinaryMetrics())
        test_row = {
            "epoch": "test_best",
            "train_loss": "",
            "train_grad_norm": "",
            "val_loss": "",
            "val_mae": "",
            "val_rmse": "",
            "val_binary_f1": "",
            "val_binary_auc_roc": "",
            "lr": "",
            "test_loss": test_metrics["loss"],
            "test_mae": test_metrics["mae"],
            "test_rmse": test_metrics["rmse"],
            "test_binary_f1": test_metrics.get("binary_f1", float("nan")),
            "test_binary_auc_roc": test_metrics.get("binary_auc_roc", float("nan")),
        }
        _write_metrics(log_path, test_row)
        logger.info("Test metrics: %s", test_metrics)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train MultimodalStressNet")
    parser.add_argument("--config-dir", type=str, default="ml_pipeline/configs")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--checkpoint-dir", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=None)
    parser.add_argument("--max-epochs", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        checkpoint_dir=args.checkpoint_dir,
        log_dir=args.log_dir,
        dry_run=args.dry_run,
        resume=args.resume,
        amp=args.amp,
        seed=args.seed,
        num_workers=args.num_workers,
        max_epochs=args.max_epochs,
    )
