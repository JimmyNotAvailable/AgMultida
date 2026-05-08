"""ONNX export for MultimodalStressNet.

Exports model with dynamic batch axis matching onnx_io_contract.yaml.
Supports dry-run mode: export with dummy tensors, reload, and verify contract.

Usage:
    python ml_pipeline/export/export_onnx.py --dry-run
    python ml_pipeline/export/export_onnx.py --checkpoint path/to/model.pt --output model.onnx
"""
from __future__ import annotations

import argparse
import logging
import pickle
import sys
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

logger = logging.getLogger("agtech.export")

# Shapes from contracts/onnx_io_contract.yaml
INPUT_SPECS = {
    "image": ("B", 4, 224, 224),
    "sensor_seq": ("B", 48, 8),
    "weather_ctx": ("B", 6),
    "modality_mask": ("B", 3),
}
OUTPUT_NAMES = ["logits", "attention_weights"]
EXPECTED_OUTPUT_DIMENSIONS = {
    "logits": ("B", 1),
    "attention_weights": ("B", 49),
}
VERIFICATION_BATCH_SIZES = (1, 2, 4)
OPSET_VERSION = 17


def make_dummy_inputs(batch_size: int = 1) -> dict[str, Tensor]:
    """Create dummy input tensors matching ONNX I/O contract."""
    return {
        "image": torch.randn(batch_size, 4, 224, 224),
        "sensor_seq": torch.randn(batch_size, 48, 8),
        "weather_ctx": torch.randn(batch_size, 6),
        "modality_mask": torch.ones(batch_size, 3),
    }


def _expected_shape(dimensions: tuple[str | int, ...], batch_size: int) -> tuple[int, ...]:
    """Resolve contract dimensions for concrete batch size."""
    return tuple(batch_size if dimension == "B" else dimension for dimension in dimensions)


def _model_size_mb(path: str | Path) -> float:
    """Return model file size in megabytes."""
    return Path(path).stat().st_size / (1024 * 1024)


def load_model_checkpoint(
    model: torch.nn.Module,
    checkpoint_path: str | Path,
    device: torch.device | str = "cpu",
    allow_unsafe_checkpoint_load: bool = False,
) -> dict[str, Any]:
    """Load weights from plain state dict or save_checkpoint wrapper.

    Returns checkpoint metadata when present. Expects wrapped checkpoints to use
    save_checkpoint's model_state_dict key.
    """
    try:
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    except pickle.UnpicklingError:
        if not allow_unsafe_checkpoint_load:
            raise
        logger.warning(
            "Using weights_only=False for trusted local checkpoint: %s",
            checkpoint_path,
        )
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        metadata = {
            "epoch": checkpoint.get("epoch"),
            "metrics": checkpoint.get("metrics", {}),
            "model_version": checkpoint.get("model_version", "unknown"),
            "config": checkpoint.get("config", {}),
        }
    elif isinstance(checkpoint, dict) and all(isinstance(value, Tensor) for value in checkpoint.values()):
        state_dict = checkpoint
        metadata = {"epoch": None, "metrics": {}, "model_version": "unknown", "config": {}}
    else:
        raise KeyError("Checkpoint must contain model_state_dict or be a plain state dict")

    model.load_state_dict(state_dict)
    logger.info("Loaded checkpoint weights from %s", checkpoint_path)
    return metadata


def export_onnx(
    model: torch.nn.Module,
    output_path: str,
    batch_size: int = 1,
    opset: int = OPSET_VERSION,
) -> dict[str, Any]:
    """Export model to ONNX format and report output metadata."""
    model.eval()
    dummy = make_dummy_inputs(batch_size)
    dummy_args = tuple(dummy[name] for name in INPUT_SPECS)

    dynamic_axes = {
        "image": {0: "batch_size"},
        "sensor_seq": {0: "batch_size"},
        "weather_ctx": {0: "batch_size"},
        "modality_mask": {0: "batch_size"},
        "logits": {0: "batch_size"},
        "attention_weights": {0: "batch_size"},
    }

    torch.onnx.export(
        model,
        dummy_args,
        output_path,
        input_names=list(INPUT_SPECS.keys()),
        output_names=OUTPUT_NAMES,
        dynamic_axes=dynamic_axes,
        opset_version=opset,
        dynamo=False,
        do_constant_folding=True,
    )

    size_mb = _model_size_mb(output_path)
    logger.info("ONNX model exported to %s (%.2f MB)", output_path, size_mb)
    return {"output_path": output_path, "model_size_mb": size_mb, "opset": opset}


def _validate_session_contract(session: Any) -> dict[str, Any]:
    """Validate ONNX Runtime session input and output names."""
    input_names = [model_input.name for model_input in session.get_inputs()]
    output_names = [model_output.name for model_output in session.get_outputs()]
    expected_input_names = list(INPUT_SPECS.keys())

    if input_names != expected_input_names:
        raise ValueError(f"ONNX input names mismatch: expected {expected_input_names}, got {input_names}")
    if output_names != OUTPUT_NAMES:
        raise ValueError(f"ONNX output names mismatch: expected {OUTPUT_NAMES}, got {output_names}")

    return {"input_names": input_names, "output_names": output_names}


def _verify_batch(session: Any, batch_size: int) -> dict[str, Any]:
    """Run one ONNX inference and verify output shapes for batch size."""
    dummy = make_dummy_inputs(batch_size)
    feed = {name: tensor.numpy() for name, tensor in dummy.items()}
    start_time = time.perf_counter()
    outputs = session.run(OUTPUT_NAMES, feed)
    latency_ms = (time.perf_counter() - start_time) * 1000

    actual_output_shapes = {
        name: tuple(output.shape) for name, output in zip(OUTPUT_NAMES, outputs)
    }
    expected_output_shapes = {
        name: _expected_shape(dimensions, batch_size)
        for name, dimensions in EXPECTED_OUTPUT_DIMENSIONS.items()
    }
    passed = actual_output_shapes == expected_output_shapes

    return {
        "batch_size": batch_size,
        "passed": passed,
        "latency_ms": latency_ms,
        "expected_output_shapes": expected_output_shapes,
        "actual_output_shapes": actual_output_shapes,
    }


def verify_onnx(
    onnx_path: str,
    batch_sizes: Iterable[int] = VERIFICATION_BATCH_SIZES,
) -> dict[str, Any]:
    """Reload exported ONNX and verify names/shapes across batch sizes."""
    import onnx
    import onnxruntime as ort

    model = onnx.load(onnx_path)
    onnx.checker.check_model(model)
    logger.info("ONNX structural check passed")

    session = ort.InferenceSession(onnx_path)
    contract_report = _validate_session_contract(session)
    batch_reports = [_verify_batch(session, batch_size) for batch_size in batch_sizes]
    all_checks_passed = all(batch_report["passed"] for batch_report in batch_reports)
    latency_values = [batch_report["latency_ms"] for batch_report in batch_reports]
    latency_ms = sum(latency_values) / max(1, len(latency_values))

    for batch_report in batch_reports:
        status = "PASS" if batch_report["passed"] else "FAIL"
        logger.info(
            "Batch %s: %s in %.2f ms",
            batch_report["batch_size"],
            status,
            batch_report["latency_ms"],
        )

    if all_checks_passed:
        logger.info("ONNX verification PASSED")
    else:
        logger.error("ONNX verification FAILED: shape mismatch")

    return {
        **contract_report,
        "all_checks_passed": all_checks_passed,
        "verified_batch_sizes": [batch_report["batch_size"] for batch_report in batch_reports],
        "batch_reports": batch_reports,
        "latency_ms": latency_ms,
        "model_size_mb": _model_size_mb(onnx_path),
    }


def dry_run() -> dict[str, Any]:
    """Export dummy model, verify, report metrics, clean up."""
    from ml_pipeline.models.network import MultimodalStressNet

    logger.info("Starting ONNX dry-run export...")
    model = MultimodalStressNet(pretrained_backbone=False)

    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as temp_file:
        onnx_path = temp_file.name

    try:
        export_report = export_onnx(model, onnx_path)
        verify_report = verify_onnx(onnx_path)
        report = {**export_report, **verify_report}
    finally:
        Path(onnx_path).unlink(missing_ok=True)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MultimodalStressNet to ONNX")
    parser.add_argument("--dry-run", action="store_true", help="Export dummy model and verify")
    parser.add_argument("--checkpoint", type=str, help="Path to model checkpoint")
    parser.add_argument("--output", type=str, default="model.onnx", help="Output ONNX path")
    parser.add_argument(
        "--allow-unsafe-checkpoint-load",
        action="store_true",
        help="Allow torch pickle fallback for trusted local checkpoints when weights_only loading fails",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.dry_run:
        report = dry_run()
        logger.info("Model size: %.2f MB", report["model_size_mb"])
        logger.info("Average latency: %.2f ms", report["latency_ms"])
        sys.exit(0 if report["all_checks_passed"] else 1)

    if not args.checkpoint:
        parser.error("--checkpoint required when not in --dry-run mode")

    from ml_pipeline.models.network import MultimodalStressNet

    model = MultimodalStressNet(pretrained_backbone=False)
    load_model_checkpoint(
        model,
        args.checkpoint,
        allow_unsafe_checkpoint_load=args.allow_unsafe_checkpoint_load,
    )
    export_report = export_onnx(model, args.output)
    verify_report = verify_onnx(args.output)
    logger.info("Model size: %.2f MB", export_report["model_size_mb"])
    logger.info("Average latency: %.2f ms", verify_report["latency_ms"])
    sys.exit(0 if verify_report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
