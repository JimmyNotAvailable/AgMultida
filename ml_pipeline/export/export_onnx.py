"""ONNX export for MultimodalStressNet.

Exports the model with dynamic batch axis matching onnx_io_contract.yaml.
Supports --dry-run mode: export with dummy tensors, reload, and verify shapes.

Usage:
    python ml_pipeline/export/export_onnx.py --dry-run
    python ml_pipeline/export/export_onnx.py --checkpoint path/to/model.pt --output model.onnx
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger("agtech.export")

# Shapes from contracts/onnx_io_contract.yaml
INPUT_SPECS = {
    "image": (1, 4, 224, 224),
    "sensor_seq": (1, 48, 8),
    "weather_ctx": (1, 6),
    "modality_mask": (1, 3),
}
OUTPUT_NAMES = ["logits", "attention_weights"]
EXPECTED_OUTPUT_SHAPES = {
    "logits": (1, 1),
    "attention_weights": (1, 49),
}
OPSET_VERSION = 17


def make_dummy_inputs(batch_size: int = 1) -> dict[str, torch.Tensor]:
    """Create dummy input tensors matching ONNX I/O contract."""
    return {
        "image": torch.randn(batch_size, 4, 224, 224),
        "sensor_seq": torch.randn(batch_size, 48, 8),
        "weather_ctx": torch.randn(batch_size, 6),
        "modality_mask": torch.ones(batch_size, 3),
    }


def export_onnx(
    model: torch.nn.Module,
    output_path: str,
    batch_size: int = 1,
    opset: int = OPSET_VERSION,
) -> str:
    """Export model to ONNX format.

    Args:
        model: MultimodalStressNet instance.
        output_path: Path to save .onnx file.
        batch_size: Batch size for dummy input.
        opset: ONNX opset version.

    Returns:
        Path to exported ONNX file.
    """
    model.eval()
    dummy = make_dummy_inputs(batch_size)
    dummy_args = (dummy["image"], dummy["sensor_seq"], dummy["weather_ctx"], dummy["modality_mask"])

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
        do_constant_folding=True,
    )
    logger.info("ONNX model exported to %s", output_path)
    return output_path


def verify_onnx(onnx_path: str, batch_size: int = 1) -> bool:
    """Reload exported ONNX and verify output shapes.

    Returns:
        True if all output shapes match contract.
    """
    import onnx
    import onnxruntime as ort

    # Structural check
    model = onnx.load(onnx_path)
    onnx.checker.check_model(model)
    logger.info("ONNX structural check passed")

    # Runtime check
    session = ort.InferenceSession(onnx_path)
    dummy = make_dummy_inputs(batch_size)
    feed = {k: v.numpy() for k, v in dummy.items()}
    outputs = session.run(None, feed)

    results = {}
    for name, output, expected_shape in zip(
        OUTPUT_NAMES, outputs, EXPECTED_OUTPUT_SHAPES.values()
    ):
        actual_shape = output.shape
        match = actual_shape == expected_shape
        results[name] = {"expected": expected_shape, "actual": actual_shape, "match": match}
        status = "PASS" if match else "FAIL"
        logger.info("  %s: %s (expected %s, got %s)", name, status, expected_shape, actual_shape)

    all_pass = all(r["match"] for r in results.values())
    if all_pass:
        logger.info("ONNX verification PASSED")
    else:
        logger.error("ONNX verification FAILED: shape mismatch")
    return all_pass


def dry_run() -> bool:
    """Export with dummy model, verify, clean up."""
    from ml_pipeline.models.network import MultimodalStressNet

    logger.info("Starting ONNX dry-run export...")
    model = MultimodalStressNet(pretrained_backbone=False)

    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
        onnx_path = f.name

    try:
        export_onnx(model, onnx_path)
        success = verify_onnx(onnx_path)
    finally:
        Path(onnx_path).unlink(missing_ok=True)

    return success


def main():
    parser = argparse.ArgumentParser(description="Export MultimodalStressNet to ONNX")
    parser.add_argument("--dry-run", action="store_true", help="Export dummy model and verify")
    parser.add_argument("--checkpoint", type=str, help="Path to model checkpoint")
    parser.add_argument("--output", type=str, default="model.onnx", help="Output ONNX path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.dry_run:
        success = dry_run()
        sys.exit(0 if success else 1)

    if not args.checkpoint:
        parser.error("--checkpoint required when not in --dry-run mode")

    from ml_pipeline.models.network import MultimodalStressNet
    model = MultimodalStressNet(pretrained_backbone=False)
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu"))
    export_onnx(model, args.output)
    verify_onnx(args.output)


if __name__ == "__main__":
    main()
