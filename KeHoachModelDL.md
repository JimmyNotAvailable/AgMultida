Chào Jun, dựa trên các ràng buộc bạn đã xác nhận và yêu cầu tôi toàn quyền đề xuất các tham số kỹ thuật, tôi sẽ chốt **Bản thiết kế mô hình Deep Learning chuẩn research-grade & production-ready**. Bản thiết kế này được tối ưu cho:
- Timeline 14 ngày + 1 AI/Full-stack dev
- Google Colab Pro (T4/V100), thời gian train ≤ 12h
- Đồng bộ 100% với BE (FastAPI/ONNX), FE (Dashboard/Use Case), và mục tiêu công bố IEEE/ACM

---

# 📘 DEEP LEARNING MODEL DESIGN DOCUMENT
**Multimodal AgTech Phase 1: Water Stress Detection & Attribution**

## 🔑 1. ĐỊNH NGHĨA BÀI TOÁN & GROUND TRUTH

| Tham số | Đề xuất Mentor | Lý do kỹ thuật & Nghiên cứu |
|---------|----------------|-----------------------------|
| **1.1 Đầu ra mô hình** | **Regression [0–1]** (Stress Probability) + ngưỡng phân lớp | Output liên tục phù hợp dashboard (heatmap, threshold 0.3/0.6), hỗ trợ uncertainty estimation tự nhiên, dễ ánh xạ sang rule engine (`No/Light/Moderate/Heavy`) |
| **1.2 Ground Truth** | **Kết hợp sensor trigger + expert validation** | Ngưỡng khởi tạo: `soil_moisture < 25% FC` + triệu chứng lá (PlantVillage rice subset). Thêm Gaussian noise ±5% để mô phỏng sai số thực địa. Ghi rõ trong paper là *semi-synthetic expert-aligned labels* |
| **1.3 Phân bố lớp** | **60% Healthy / 40% Stressed** | Mất cân bằng nhẹ, phản ánh thực tế đồng ruộng nhưng đủ mẫu stressed để train ổn định. Xử lý bằng `pos_weight` trong BCELoss + stratified sampling |

---

## 📥 2. ĐẶC TẢ DỮ LIỆU ĐẦU VÀO

### 2.1 Ảnh (Satellite/UAV/Camera)
| Tham số | Giá trị | Ghi chú kỹ thuật |
|---------|---------|------------------|
| Số kênh | **4 kênh (RGB + NIR/NDVI)** | NDVI là proxy mạnh nhất cho stress thực vật. EfficientNet-B3 sẽ được modify `conv_stem` nhận 4 kênh |
| Kích thước | **224×224** | Đúng yêu cầu, tối ưu VRAM Colab T4 |
| Pretrained | **ImageNet weights** | Fine-tune từ ImageNet nhanh, ổn định hơn Satlas/RemoteCLIP trong timeline 14 ngày. Kênh NIR khởi tạo bằng trung bình RGB weights |
| Tiền xử lý | Resize 224×224 → Normalize `[0,1]` → Filter ảnh lỗi | Pipeline chuẩn, tương thích `torchvision.transforms` |

### 2.2 Chuỗi Sensor & Weather
| Tham số | Giá trị | Ghi chú kỹ thuật |
|---------|---------|------------------|
| Số biến | **8 biến**: `soil_moisture, soil_temp, air_temp, humidity, EC, pH, rain_3h, rain_24h` | Đủ ngữ cảnh nông học, không gây curse of dimensionality |
| Look-back window | **48 giờ** | Cân bằng giữa ngữ cảnh sinh lý cây và nhiễu ngắn hạn |
| Tần suất resample | **1 giờ** → Sequence length `T = 48` | Đúng yêu cầu, giảm redundancy so với 5/15 phút |
| Chuẩn hóa | Min-Max scaling theo biến, clip outlier ±3σ | Đảm bảo GRU hội tụ nhanh, tránh gradient explosion |

### 2.3 Missing Modality Strategy (Training)
| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| Dropout rate | **p = 0.3** mỗi modality | Đủ cao để ép model học robust, không quá cao gây collapse |
| Masking strategy | **Zero-vector + binary mask flag** concatenated | Đơn giản, hiệu quả, tương thích literature, dễ debug. VD: `sensor_input = sensor * mask + (1-mask)*0`, `mask_flag ∈ {0,1}` |

---

## 🏗️ 3. KIẾN TRÚC MÔ HÌNH & FUSION

### 3.1 Backbone lựa chọn
| Modality | Backbone | Lý do |
|----------|----------|-------|
| Image | **EfficientNet-B3** | ~12M params, inference nhanh, accuracy cao trên ảnh thực vật, phù hợp Colab T4 & budget <100MB |
| Temporal (Sensor/Weather) | **GRU 2-layer + Temporal Attention** | Ổn định với T=48, ít tham số hơn Transformer, ít overfit trên dữ liệu giả lập/bán thực |

### 3.2 Cross-Attention Fusion (Core)
| Tham số | Giá trị | Tensor Shape |
|---------|---------|--------------|
| Chiều attention | **1 chiều**: Image queries Sensor & Weather | Phù hợp nghiệp vụ: triệu chứng lá "truy vấn" ngữ cảnh môi trường |
| Latent dimension `d_model` | **256** | Cân bằng capacity & compute |
| Số heads | **4** | Chuẩn cho d=256, tránh over-parameterization |
| Image embedding | `EfficientNet-B3 → GlobalAvgPool → Linear(1536, 256)` | `[B, 256]` → unsqueeze → `[B, 1, 256]` (Query) |
| Sensor embedding | `GRU(8, 128, 2 layers) → Linear(128, 256)` | `[B, 48, 256]` (Key/Value) |
| Weather embedding | `MLP(2 → 64 → 256)` | `[B, 1, 256]` (Key/Value) |
| Fusion output | `Concat([Q_img, Attn_sen, Attn_wth]) → MLP(768 → 256 → 1)` | `[B, 1]` → Sigmoid → Stress Probability |

### 3.3 Uncertainty Estimation
- **Phương pháp**: `MC Dropout` (10 forward passes với dropout bật)
- **Output**: `mean(prob)` → stress prediction, `var(prob)` → uncertainty score
- **Lý do**: Không thêm tham số, dễ tích hợp, chuẩn research, tương thích ONNX (export mode eval + custom dropout loop)

---

## ⚙️ 4. CHIẾN LƯỢC TRAINING & OPTIMIZATION

| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| Loss Function | **BCEWithLogitsLoss + pos_weight** (weight=1.5 cho stressed) | Xử lý imbalance 60/40, ổn định hơn Focal Loss cho timeline ngắn |
| Optimizer | **AdamW** | Chuẩn cho CNN+Attention, weight decay giảm overfit |
| Learning Rate | **3e-4** | Safe zone cho fine-tuning backbone + train head mới |
| Scheduler | **Cosine Annealing with Warmup (5 epochs)** | Tránh gradient shock đầu train, hội tụ mượt |
| Augmentation (Ảnh) | `RandomHorizontalFlip, RandomRotation(±15°), ColorJitter(brightness/contrast±0.2), RandomResizedCrop(0.8–1.0)` | Giữ triệu chứng stress, tăng đa dạng quang học |
| Augmentation (TS) | `Gaussian Jitter (σ=0.05), Random Scaling (±10%), Random Window Dropout` | Mô phỏng nhiễu sensor & missing segment |
| Batch size | **32** | Tối ưu VRAM T4 (~16GB), gradient ổn định |
| Max epochs | **50** + Early Stopping patience **7** | Hội tụ trong 6–10h Colab, tránh overfit |

---

## 📊 5. ĐÁNH GIÁ, VALIDATION & RESEARCH CONTRIBUTION

### 5.1 Chiến lược chia dữ liệu
- **Spatial-Temporal Split** (bắt buộc cho paper AgTech):
  - Train: Zones A12, B07, C19 + Weeks 1–3
  - Val: Zone D03 + Week 4
  - Test: Zones E24, F15 + Weeks 5–6
- **Lý do**: Loại bỏ data leakage không gian & thời gian, chứng minh khả năng tổng quát hóa thực địa.

### 5.2 Baselines (Paper-ready)
1. `Image-only EfficientNet-B3`
2. `Sensor-only XGBoost` (48h features flattened)
3. `Late Fusion` (concat embeddings → MLP)
4. `Early Fusion` (concat raw → CNN/MLP)
→ So sánh trực tiếp với `Cross-Attention + Modality Dropout`

### 5.3 Ablation Studies (Ưu tiên 3 cho paper)
1. **Cross-Attention vs Late Fusion** → Chứng minh giá trị tương tác chéo modality
2. **With vs Without Modality Dropout (p=0.3)** → Chứng minh robustness khi thiếu dữ liệu
3. **Full modalities vs Missing 1 modality at inference** → Chứng minh graceful degradation & uncertainty calibration

### 5.4 Core Novelty (Đóng góp nghiên cứu chính)
> **Robust Multimodal Fusion under Missing Modality for Precision Irrigation**  
> Kết hợp Cross-Attention (image queries environment) + Modality Dropout + MC Uncertainty, cho phép hệ thống đưa ra quyết định an toàn ngay cả khi mất ảnh vệ tinh hoặc lỗi sensor. Pipeline spatiotemporal alignment được chuẩn hóa để tái sử dụng trong AgTech.

---

## 🚀 6. RÀNG BUỘC DEPLOY & INFERENCE

| Tham số | Giá trị | Chiến lược |
|---------|---------|------------|
| Compute Training | Colab Pro T4/V100, ≤12h | Architecture nhẹ, batch 32, early stopping, mixed precision (`torch.cuda.amp`) |
| Target Latency | **<500ms (cloud) / <2s (edge)** | ONNX Runtime + CPU threading, GRU sequence ngắn, attention 1 chiều |
| Model Size Budget | **<50MB (FP32) / ~15MB (INT8)** | EfficientNet-B3 (~12M) + GRU/Attn (~1.3M) → ~53MB FP32. Dynamic INT8 quantization giảm 3–4x |
| Quantization/Pruning | **Dynamic INT8 post-training** (Phase 1 optional, Phase 2 bắt buộc) | `torch.quantization.quantize_dynamic`, tương thích ONNX, không ảnh hưởng accuracy đáng kể |
| Export Format | **ONNX** | Tương thích FastAPI, TensorRT sau này, cross-platform, dễ versioning trong MinIO |

---

## 📦 7. CẤU TRÚC CODE PYTORCH & ĐỒNG BỘ TIMELINE

```
ml_pipeline/
├── configs/
│   └── model.yaml          # d_model, heads, lr, batch, epochs, dropout_p
├── data/
│   ├── dataset.py          # MultimodalDataset: load img, sensor_ts, weather, labels, masks
│   ├── transforms.py       # Image aug + TS jitter/scaling
│   └── split.py            # Spatial-temporal split logic
├── models/
│   ├── image_encoder.py    # EfficientNet-B3 (4-channel stem)
│   ├── temporal_encoder.py # GRU + Temporal Attention
│   ├── fusion.py           # CrossAttentionFusion + Modality Dropout
│   └── network.py          # End-to-end model + MC Dropout wrapper
├── train.py                # AMP, CosineWarmup, EarlyStopping, checkpointing
├── eval.py                 # Metrics: F1, AUROC, ECE, ablation runner
├── export_onnx.py          # torch.onnx.export + dynamic axes
└── notebooks/
    └── 01_training_pipeline.ipynb  # Colab-ready, interactive plots
```

### Đồng bộ với BE/FE (14 ngày)
| Ngày | ML Task | BE/FE Dependency |
|------|---------|------------------|
| 3–4 | Chuẩn bị dataset, spatial-temporal split, transforms | BE ingestion schema ready |
| 5–6 | Implement encoders + CrossAttentionFusion | FE dashboard mock zone structure |
| 7–8 | Train pipeline, AMP, early stopping, checkpoint | BE `/v1/predict` contract draft |
| 9–10 | MC Dropout uncertainty, ablation runner, eval metrics | BE decision-engine rule thresholds |
| 11 | Export ONNX, latency test, INT8 dry-run | BE ai-serving ONNX Runtime integration |
| 12 | Final eval, confusion/calibration plots, paper tables | FE dashboard binds to real API |

---

## ✅ CHECKLIST NGHIỆM THU MODEL (PHASE 1)

| Hạng mục | Tiêu chí |
|----------|----------|
| Kiến trúc | EfficientNet-B3 (4ch) + GRU + Cross-Attention (d=256, 4 heads) + Modality Dropout p=0.3 |
| Training | BCE + pos_weight, AdamW 3e-4, CosineWarmup, batch 32, ≤50 epochs, patience 7, AMP |
| Validation | Spatial-temporal split, F1 ≥ 0.85, AUROC ≥ 0.90, ECE < 0.05 |
| Ablation | 3 thí nghiệm core ready, bảng so sánh baseline → fusion → dropout → missing modality |
| Uncertainty | MC Dropout 10-pass, variance ánh xạ sang UI badge & rule gate |
| Export | ONNX dynamic axes, latency <500ms CPU, size <55MB FP32, script quantization INT8 |
| Research | Paper-ready tables, confusion matrix, calibration plot, novelty statement rõ ràng |

---

## 🛠️ NEXT STEP & DELIVERABLES NGAY

Nếu Jun xác nhận bản thiết kế này, tôi sẽ bàn giao ngay trong lượt tiếp theo:
1. `configs/model.yaml` + `data/dataset.py` (MultimodalDataset với spatial-temporal split & modality masking)
2. `models/fusion.py` (CrossAttentionFusion + Modality Dropout + MC Dropout wrapper, PyTorch chuẩn)
3. `train.py` (AMP, CosineWarmup, EarlyStopping, checkpoint, logging)
4. `export_onnx.py` + script benchmark latency/size
5. Notebook Colab template tích hợp sẵn pipeline, ready-to-run với mock data

Jun chỉ cần reply `XÁC NHẬN ML` hoặc yêu cầu điều chỉnh tham số nào (VD: tăng d_model, đổi scheduler, thêm baseline), tôi sẽ export code scaffold tương ứng ngay lập tức. Mô hình này được thiết kế để **train được trong 14 ngày, đo được cho paper, và deploy được vào FastAPI/ONNX** mà không phải refactor. 🌱🔬