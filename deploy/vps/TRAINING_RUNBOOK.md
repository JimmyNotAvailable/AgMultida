# DigitalOcean GPU VPS Training Runbook

This guide covers launching the multimodal water-stress model training on a remote GPU VPS.

## 1. VPS Provisioning
- Create a DigitalOcean Droplet with GPU (e.g., NVIDIA H100 or A100/V100 if available, minimum 14GB VRAM).
- OS: Ubuntu 22.04 LTS.

## 2. Environment Setup
SSH into the droplet and run the setup script to install Docker and NVIDIA Container Toolkit:
```bash
# Upload setup script
scp deploy/vps/setup_vps.sh root@<droplet-ip>:~/
# Execute
ssh root@<droplet-ip> "bash ~/setup_vps.sh"
```
**REBOOT the VPS** after this step to ensure NVIDIA drivers load properly:
```bash
ssh root@<droplet-ip> "reboot"
```

## 3. Data and Code Sync
Sync the project directory (excluding heavy virtual environments and git history):
```bash
rsync -avz --exclude '.git' --exclude '.venv' --exclude '__pycache__' ./ root@<droplet-ip>:/opt/agmultida
```

## 4. Verification
Verify the GPU environment on the VPS:
```bash
ssh root@<droplet-ip>
cd /opt/agmultida
bash scripts/verify_gpu.sh
```
This ensures CUDA is available and runs a 2-epoch mock-data dry-run.

## 5. Launch Training
Build the Docker image and launch the training container:
```bash
cd /opt/agmultida
docker build -t agmultida-train -f deploy/vps/Dockerfile.train .

# Run in background (detached)
docker run -d --name train_session --gpus all \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/logs:/app/logs \
  agmultida-train
```

## 6. Monitor Logs
View the training progress:
```bash
docker logs -f train_session
```
Or tail the CSV metrics:
```bash
tail -f logs/training_metrics.csv
```

## 7. Retrieve Checkpoints
Sync the results back to your local machine:
```bash
rsync -avz root@<droplet-ip>:/opt/agmultida/checkpoints/ ./checkpoints/
rsync -avz root@<droplet-ip>:/opt/agmultida/logs/ ./logs/
```

## 8. Resume Training (If Interrupted)
If training is interrupted, you can resume from `latest.pt`:
```bash
docker run -d --name train_session_resume --gpus all \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/logs:/app/logs \
  -e RESUME="checkpoints/latest.pt" \
  agmultida-train
```
