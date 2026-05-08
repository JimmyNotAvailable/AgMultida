# VPS Training Quick Commands

*Copy-paste these commands to quickly deploy and run training on DigitalOcean GPU.*

## 1. Initial Setup on Droplet
*Run on VPS (SSH session).*

```bash
# Setup Git & Workspace
sudo mkdir -p /workspace/agtech
sudo chown -R "$USER:$USER" /workspace/agtech
```

## 2. Sync Code & Data
*Run on Local Machine.*

```bash
export DROPLET_IP="your_droplet_ip"
# Dry-run
rsync -avzn --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ root@$DROPLET_IP:/workspace/agtech/AgMultida
# Real sync
rsync -avz --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ root@$DROPLET_IP:/workspace/agtech/AgMultida
```

## 3. Install Drivers & Verify
*Run on VPS.*

```bash
cd /workspace/agtech/AgMultida
bash deploy/vps/setup_vps.sh

# REBOOT REQUIRED after drivers install
sudo reboot
```
*Wait for reboot, then reconnect via SSH.*

```bash
cd /workspace/agtech/AgMultida
# Verify GPU (expect PASS)
bash scripts/verify_gpu.sh
```

## 4. Launch Training
*Run on VPS.*

```bash
cd /workspace/agtech/AgMultida
# Build Docker image
docker build -t agmultida-train -f deploy/vps/Dockerfile.train .

# Run training in background
docker run -d --name train_session --gpus all \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/logs:/app/logs \
  agmultida-train
```

## 5. Monitor
*Run on VPS.*

```bash
# Watch metrics
tail -f logs/training_metrics.csv
# Or watch container logs
docker logs -f train_session
# Watch GPU usage
watch -n 2 nvidia-smi
```

## 6. Retrieve Results & Teardown
*Run on Local Machine.*

```bash
# Download models and logs
mkdir -p backups/do_run_001
rsync -avz root@$DROPLET_IP:/workspace/agtech/AgMultida/checkpoints/ ./backups/do_run_001/checkpoints/
rsync -avz root@$DROPLET_IP:/workspace/agtech/AgMultida/logs/ ./backups/do_run_001/logs/

# Generate checksums locally
cd backups/do_run_001
find . -type f -exec sha256sum {} \; > SHA256SUMS
```

*Finally: Destroy droplet from DigitalOcean Dashboard to stop billing.*
