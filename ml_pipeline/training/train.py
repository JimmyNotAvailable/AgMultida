"""Training loop skeleton and checkpoint management.

Pure functions for train_one_epoch, evaluate, save_checkpoint, load_checkpoint.
Supports AMP (Automatic Mixed Precision) safely falling back on CPU.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.amp import GradScaler, autocast

from ml_pipeline.training.metrics import BinaryMetrics

logger = logging.getLogger(__name__)


def train_one_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler],
    scaler: GradScaler,
    device: torch.device,
) -> dict[str, float]:
    """Run one training epoch.

    Returns:
        dict with "loss" representing average loss over the epoch.
    """
    model.train()
    total_loss = 0.0
    num_batches = len(dataloader)

    # AMP is safe on CPU if scaler enabled=False and autocast device_type="cpu" or "cuda"
    device_type = "cuda" if device.type == "cuda" else "cpu"
    amp_enabled = scaler.is_enabled()

    for batch_idx, batch in enumerate(dataloader):
        # Move tensors to device
        inputs = {
            k: v.to(device)
            for k, v in batch.items()
            if k != "label"
        }
        labels = batch["label"].to(device)

        optimizer.zero_grad(set_to_none=True)

        with autocast(device_type=device_type, enabled=amp_enabled):
            logits, _ = model(**inputs)
            loss = loss_fn(logits, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        if scheduler is not None:
            scheduler.step()

        total_loss += loss.item()

    avg_loss = total_loss / max(1, num_batches)
    return {"loss": avg_loss}


@torch.no_grad()
def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    loss_fn: nn.Module,
    metrics: BinaryMetrics,
    device: torch.device,
) -> dict[str, float]:
    """Run evaluation pass.

    Returns:
        dict containing loss and all computed metrics.
    """
    model.eval()
    total_loss = 0.0
    num_batches = len(dataloader)
    metrics.reset()

    for batch in dataloader:
        inputs = {
            k: v.to(device)
            for k, v in batch.items()
            if k != "label"
        }
        labels = batch["label"].to(device)

        logits, _ = model(**inputs)
        loss = loss_fn(logits, labels)

        total_loss += loss.item()
        metrics.update(logits, labels)

    avg_loss = total_loss / max(1, num_batches)
    
    try:
        results = metrics.compute()
    except ValueError:
        results = {}

    results["loss"] = avg_loss
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
) -> None:
    """Save training state to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
        "metrics": metrics,
        "model_version": model_version,
        "config": config or {},
    }
    torch.save(state, path)
    logger.info(f"Saved checkpoint to {path}")


def load_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    device: Optional[torch.device] = None,
) -> dict[str, Any]:
    """Load checkpoint and return metadata."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    state = torch.load(path, map_location=device, weights_only=False)
    
    # Handle DDP/DataParallel prefixes if necessary, but standard load for now
    model.load_state_dict(state["model_state_dict"])

    if optimizer is not None and state.get("optimizer_state_dict"):
        optimizer.load_state_dict(state["optimizer_state_dict"])

    if scheduler is not None and state.get("scheduler_state_dict"):
        scheduler.load_state_dict(state["scheduler_state_dict"])

    logger.info(f"Loaded checkpoint from {path} (epoch {state.get('epoch')})")
    
    return {
        "epoch": state.get("epoch", 0),
        "metrics": state.get("metrics", {}),
        "model_version": state.get("model_version", "unknown"),
        "config": state.get("config", {}),
    }


def main(config_path: str | Path) -> None:
    """Entry point for training skeleton. 
    Not fully implemented for real training, meant to be called by scripts.
    """
    pass
