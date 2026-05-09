# DigitalOcean RTX 4000 Ada Training Guide

Owner: Anh Nhat Tu  
Project: AgMultida Phase 3 ML Training  
Mode: Survey and prep only  
Target: DigitalOcean GPU Droplet `gpu-4000adax1-20gb`

## 1. Mục tiêu và cảnh báo billing

Guide này chuẩn bị môi trường DigitalOcean RTX 4000 Ada để chạy training water-stress Phase 1/3 sau này. Phạm vi hiện tại không tạo droplet, không kích hoạt billing, không chạy training thật, không push DVC remote.

Cảnh báo quan trọng:

```text
GPU Droplet tính tiền theo thời gian tồn tại của droplet.
Sau khi training xong phải backup checkpoint/export rồi destroy droplet.
Không được destroy nếu chưa verify backup local.
```

Cost-control bắt buộc:

| Gate | Yêu cầu |
| --- | --- |
| Billing alert | Tạo alert trong DigitalOcean trước khi train |
| Planned runtime | 8-12h training + 1-2h setup/export |
| Idle shutdown | Đặt reminder/cron sau 30 phút idle |
| Backup | Bắt buộc trước destroy |
| Destroy | Chỉ thực hiện sau `--confirm YES` |

## 2. Spec map RTX 4000 Ada

DigitalOcean docs ghi RTX 4000 Ada self-serve GPU Droplet có slug `gpu-4000adax1-20gb`, 20GB GPU memory, 32GiB RAM, 8 vCPU, 500GiB NVMe boot disk, không có scratch disk, 10TB transfer. Tất cả GPU Droplets có max bandwidth 10Gbps public và 25Gbps private.

| Layer | Decision |
| --- | --- |
| Droplet size | `gpu-4000adax1-20gb` |
| GPU | NVIDIA RTX 4000 Ada |
| VRAM | 20GB |
| RAM | 32GiB |
| vCPU | 8 |
| Disk | 500GiB NVMe boot disk |
| OS | Ubuntu 22.04 LTS or DO AI/ML-ready NVIDIA image |
| Python | 3.11 |
| PyTorch | Linux pip wheel with CUDA 12.1+ via `deploy/vps/requirements_gpu.txt` |
| Precision | AMP fp16 default |

Recommended install path:

1. Ưu tiên DigitalOcean AI/ML-ready NVIDIA GPU image nếu có.
2. Nếu dùng Ubuntu plain image, cài NVIDIA driver theo DO recommended GPU setup, reboot, verify `nvidia-smi`.
3. Dùng Docker image của repo (`deploy/vps/Dockerfile.train`) hoặc cài đúng wheel CUDA Linux.

Verification commands:

```bash
nvidia-smi
python3 --version
python3 - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0))
    print("capability", torch.cuda.get_device_capability(0))
PY
```

## 3. Droplet setup checklist

```bash
sudo apt-get update
sudo apt-get install -y git rsync tmux htop nvtop python3-pip
sudo mkdir -p /workspace/agtech
sudo chown -R "$USER:$USER" /workspace/agtech
```

Recommended: dùng script repo hiện có.

```bash
bash deploy/vps/setup_vps.sh
sudo reboot
```

Sau reboot:

```bash
cd /workspace/agtech/AgMultida
bash scripts/verify_gpu.sh
```

## 4. Data sync từ local lên DO

Repo hiện tại chưa có `sync_to_do.sh` hay `teardown_do.sh`. Cách chuẩn là dùng `rsync`.

Dry-run:

```bash
rsync -avzn --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ root@DROPLET_IP:/workspace/agtech/AgMultida
```

Real sync:

```bash
rsync -avz --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ root@DROPLET_IP:/workspace/agtech/AgMultida
```

Data training mục tiêu hiện tại:

```text
data/processed_real/
```

Sau sync, remote validation:

```bash
cd /workspace/agtech/AgMultida
python3 - <<'PY'
import json
from pathlib import Path
p = Path('data/processed_real/dataset_readiness_report.json')
print(json.loads(p.read_text()))
PY
```

Lưu ý: local report cho thấy một số `.npy` có thể bị zero-byte nếu copy sai. Cần verify data thật trước full training.

## 5. Config training cho RTX 4000 Ada

Training entrypoint thật hiện tại:

```bash
python3 -m ml_pipeline.training.train \
  --config-dir ml_pipeline/configs \
  --data-dir data/processed_real \
  --checkpoint-dir checkpoints \
  --log-dir logs \
  --amp \
  --seed 42 \
  --num-workers 4 \
  --max-epochs 50
```

Config lock hiện tại:

| Setting | Value |
| --- | --- |
| scheduler | `one_cycle_lr` |
| weather_dim | `6` |
| seed | `42` |
| AMP | `true` |
| grad_clip_norm | `1.0` |
| num_workers | `4` |
| pin_memory | `true` when CUDA |
| prefetch_factor | `2` |
| persistent_workers | `true` when num_workers > 0 |

Training architecture:

```text
EfficientNet-B3 4ch -> GRU(8->128, 2-layer) -> CrossAttention(d=256, heads=4)
Loss: ProxyRegressionLoss (MSE on sigmoid outputs)
Optimizer: AdamW(lr=3e-4, wd=1e-4)
Scheduler: OneCycleLR(max_lr=3e-4, pct_start=0.1)
Epochs: 50
Early stopping: patience=7
```

Resource estimate:

| Batch | Expected use |
| ---: | --- |
| 48 | Primary RTX 4000 Ada run, target <=18GB VRAM |
| 32 | Fallback if first dry step exceeds 18GB |
| 16 | Emergency fallback after OOM |

Before full training:

```bash
python3 -m pytest tests/ml -v
bash scripts/verify_gpu.sh
```

## 6. Monitoring trong lúc train

Chạy trong `tmux` để tránh mất session:

```bash
tmux new -s agtech-train
```

Monitoring GPU:

```bash
watch -n 5 nvidia-smi
```

Monitoring disk:

```bash
df -h /workspace /workspace/agtech
du -sh /workspace/agtech/*
```

Monitoring logs:

```bash
tail -f /workspace/agtech/AgMultida/logs/training_metrics.csv
docker logs -f train_session
```

Stop conditions:

| Condition | Action |
| --- | --- |
| VRAM >19GB | Stop, reduce batch to 32 or 16 |
| NaN/Inf loss | Stop, reduce LR to `1e-4`, verify scaler and tensor ranges |
| Val RMSE/MAE worsens continuously after epoch 5 | Continue only if trend improves; otherwise inspect proxy-label quality/data split |
| Disk free <50GB | Stop and backup before cleanup |

## 7. Launch bằng Docker

Build image:

```bash
cd /workspace/agtech/AgMultida
docker build -t agmultida-train -f deploy/vps/Dockerfile.train .
```

Run training:

```bash
docker run -d --name train_session --gpus all \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/logs:/app/logs \
  agmultida-train
```

Resume training:

```bash
docker run -d --name train_session_resume --gpus all \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/logs:/app/logs \
  -e RESUME="checkpoints/latest.pt" \
  agmultida-train
```

## 8. Backup và teardown

Repo hiện chưa có script teardown tự động. Cách an toàn:

```bash
rsync -avz root@DROPLET_IP:/workspace/agtech/AgMultida/checkpoints/ ./backups/do_rtx4000/run_001/checkpoints/
rsync -avz root@DROPLET_IP:/workspace/agtech/AgMultida/logs/ ./backups/do_rtx4000/run_001/logs/
```

Tạo checksum local:

```bash
cd backups/do_rtx4000/run_001
find . -type f -exec sha256sum {} \; > SHA256SUMS
```

Chỉ destroy droplet sau khi verify backup.

## 9. Troubleshooting

| Issue | Diagnosis | Fix |
| --- | --- | --- |
| `torch.cuda.is_available()` false | Driver/wheel mismatch | Check `nvidia-smi`; reinstall container/runtime or PyTorch CUDA wheel |
| OOM at batch 48 | VRAM estimate too high | Set batch 32, then 16 if needed |
| rsync slow | Network or checksum overhead | Let first sync finish; subsequent syncs are incremental |
| zero-byte `.npy` | Broken copy / incomplete artifact restore | Re-sync data or restore from DVC/source before train |
| no checkpoints/logs | Training entrypoint not writing paths | Check `CHECKPOINT_DIR`, `LOG_DIR`, mounted volumes |
| `docker --gpus all` fails | NVIDIA container toolkit not configured | Re-run `deploy/vps/setup_vps.sh`, verify `nvidia-ctk` |

## 10. Final readiness checklist

```text
[ ] Billing alert enabled in DigitalOcean
[ ] Droplet is RTX 4000 Ada slug gpu-4000adax1-20gb
[ ] nvidia-smi PASS
[ ] torch CUDA verification PASS
[ ] deploy/vps/setup_vps.sh completed
[ ] scripts/verify_gpu.sh PASS on droplet
[ ] rsync dry-run reviewed
[ ] rsync real sync completed
[ ] dataset_readiness_report.json verified on droplet
[ ] tests/ml PASS or known non-blocking gaps documented
[ ] tmux session ready
[ ] checkpoints/logs paths writable
[ ] backup copied back locally before destroy
```

## Sources

- [DigitalOcean Droplet features and GPU specs](https://docs.digitalocean.com/products/droplets/details/features/)
- [DigitalOcean recommended GPU setup](https://docs.digitalocean.com/products/droplets/getting-started/recommended-gpu-setup/)
- [PyTorch local installation selector](https://pytorch.org/get-started/locally/)
