#!/usr/bin/env bash
set -euo pipefail

echo "[TRAIN] Starting multimodal water-stress training..."

export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-4}
export PYTHONUNBUFFERED=1

DATA_DIR=${DATA_DIR:-data/aligned/v1_water_stress}
CHECKPOINT_DIR=${CHECKPOINT_DIR:-checkpoints}
LOG_DIR=${LOG_DIR:-logs}
MAX_EPOCHS=${MAX_EPOCHS:-50}
NUM_WORKERS=${NUM_WORKERS:-4}
RESUME_ARG=""
if [[ -n "${RESUME:-}" ]]; then
  RESUME_ARG="--resume ${RESUME}"
fi

mkdir -p "${CHECKPOINT_DIR}" "${LOG_DIR}"

python3 -m ml_pipeline.training.train \
  --config-dir ml_pipeline/configs \
  --data-dir "${DATA_DIR}" \
  --checkpoint-dir "${CHECKPOINT_DIR}" \
  --log-dir "${LOG_DIR}" \
  --amp \
  --seed 42 \
  --num-workers "${NUM_WORKERS}" \
  --max-epochs "${MAX_EPOCHS}" \
  ${RESUME_ARG} \
  2>&1 | tee "${LOG_DIR}/train_$(date +%Y%m%d_%H%M%S).log"

echo "[TRAIN] Finished. Checkpoints saved in ${CHECKPOINT_DIR}/"
