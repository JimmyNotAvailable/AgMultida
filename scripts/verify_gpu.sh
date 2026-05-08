#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH=${1:-reports/gpu_dryrun.json}
mkdir -p $(dirname "$REPORT_PATH")

echo "Verifying GPU Environment..."
PYTHON_BIN=${PYTHON_BIN:-python3}

if ! command -v nvidia-smi &> /dev/null; then
  echo "FAIL: nvidia-smi not found. Are NVIDIA drivers installed?"
  exit 1
fi

nvidia-smi

${PYTHON_BIN} - <<EOF
import torch
import json

def verify():
    report = {
        "cuda_available": torch.cuda.is_available(),
        "device_count": 0,
        "devices": [],
        "torch_version": torch.__version__,
        "pass": False,
        "errors": []
    }

    if not report["cuda_available"]:
        report["errors"].append("CUDA is not available.")
        with open("$REPORT_PATH", "w") as f:
            json.dump(report, f, indent=2)
        print("FAIL: CUDA is not available.")
        exit(1)

    report["device_count"] = torch.cuda.device_count()
    for i in range(report["device_count"]):
        props = torch.cuda.get_device_properties(i)
        vram_gb = props.total_memory / 1e9
        report["devices"].append({
            "name": props.name,
            "vram_gb": vram_gb
        })
        if vram_gb < 14.0:
            report["errors"].append(f"Device {i} VRAM ({vram_gb:.1f}GB) is below 14GB minimum.")

    if report["errors"]:
        with open("$REPORT_PATH", "w") as f:
            json.dump(report, f, indent=2)
        print("FAIL: GPU requirements not met.")
        print(report["errors"])
        exit(1)

    report["pass"] = True
    with open("$REPORT_PATH", "w") as f:
        json.dump(report, f, indent=2)
    print("PASS: GPU verified.")

if __name__ == "__main__":
    verify()
EOF

echo "Running 2-batch GPU Dry-Run..."
${PYTHON_BIN} -m ml_pipeline.training.train --dry-run || { echo "FAIL: Dry-run crashed."; exit 1; }
echo "PASS: GPU Dry-Run successful."
