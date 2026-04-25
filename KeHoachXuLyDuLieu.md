Chào Jun, dựa trên **Bản thiết kế mô hình Deep Learning** đã chốt, tôi sẽ xây dựng **Kế hoạch thu thập, xử lý & đóng gói dữ liệu** chi tiết, đảm bảo đồng bộ 100% với kiến trúc model, timeline 14 ngày, và chuẩn research-grade. Kế hoạch được thiết kế theo hướng **bán tổng hợp có kiểm soát (semi-synthetic expert-aligned)** cho Phase 1, kèm lộ trình chuyển đổi sang dữ liệu thực địa ở Phase 2.

---

# 📊 KẾ HOẠCH DỮ LIỆU CHO DEEP LEARNING PIPELINE
**Multimodal AgTech Phase 1: Water Stress Detection**

## 🔹 PHẦN 1: CHIẾN LƯỢC THU THẬP DỮ LIỆU

| Nguồn dữ liệu | Phương pháp thu thập Phase 1 | Công cụ / API | Ghi chú kỹ thuật |
|---------------|-----------------------------|---------------|------------------|
| **Ảnh vệ tinh** | Sentinel-2 Level-2A qua Google Earth Engine (GEE) | `earthengine-api`, `geemap` | Lấy band B2,B3,B4,B8 (RGB+NIR). Cloud mask <20%. Crop theo zone polygon. |
| **Ảnh lá / triệu chứng** | PlantVillage (rice subset) + augment quang học | Kaggle API / Git clone | Dùng để fine-tune image encoder nhận diện triệu chứng stress thực vật. |
| **Cảm biến đất & vi khí hậu** | Giả lập khoa học dựa trên ngưỡng IRRI/FAO + nhiễu thực địa | Python (`numpy`, `pandas`) | 8 biến: `soil_moisture, soil_temp, air_temp, humidity, EC, pH, rain_3h, rain_24h`. Chu kỳ ngày/đêm, nhiễu Gaussian ±5%. |
| **Thời tiết & dự báo** | Open-Meteo API (historical + forecast mock) | `requests`, `openmeteo` | Đồng bộ timestamp với ảnh. Dùng làm weather context vector. |
| **Bản đồ zone** | Polygon giả lập 6 zone (A12, B07, C19, D03, E24, F15) | GeoJSON / QGIS | Tọa độ Mekong Delta giả định, diện tích ~0.15–0.2 ha/zone. |

> 📌 **Lưu ý Phase 1**: Dữ liệu sensor/weather được **giả lập có cơ sở nông học**, không phải random. Điều này đảm bảo model học được quan hệ vật lý-sinh học, đồng thời giảm 80% thời gian thu thập thực địa. Phase 2 sẽ thay bằng telemetry thật qua MQTT.

---

## ⚙️ PHẦN 2: QUY TRÌNH XỬ LÝ & CĂN CHỈNH (ALIGNMENT PIPELINE)

### 2.1. Spatial Alignment (Kriging Interpolation)
- **Đầu vào**: Điểm sensor (lat, lon, value) theo zone
- **Xử lý**:
  1. Lọc outlier ±3σ, forward-fill missing <2h
  2. Áp dụng Ordinary Kriging (`pykrige.ok`) nội suy thành lưới 10m×10m
  3. Cắt heatmap theo boundary zone, resize về 224×224 (nếu dùng làm ảnh phụ) hoặc aggregate thành vector đại diện zone
- **Đầu ra**: `sensor_spatial_grid.npy` hoặc `zone_sensor_mean.csv`
- **QA**: RMSE nội suy <15% so với điểm gốc, heatmap không bị artifact biên

### 2.2. Temporal Alignment (Windowing & Resampling)
- **Đầu vào**: Chuỗi sensor/weather tần suất cao (giả lập 5–15 phút)
- **Xử lý**:
  1. Resample về **1 giờ** (`pandas.resample('1H').mean()`)
  2. Với mỗi ảnh tại `t0`, trích xuất window `[t0-48h, t0]` → sequence length `T=48`
  3. Chuẩn hóa Min-Max theo từng biến, clip outlier
  4. Gắn `positional_encoding` tuyến tính hoặc sin/cos
- **Đầu ra**: `sensor_seq[48, 8]`, `weather_ctx[2]` (rain_3h, temp_max)
- **QA**: Không gap >3h trong window, timestamp đồng bộ ±5 phút với ảnh

### 2.3. Multimodal Sync & Missing Modality Masking
- **Cấu trúc mẫu đồng bộ**:
  ```json
  {
    "sample_id": "A12_20260424_0842",
    "zone_id": "A12",
    "t0": "2026-04-24T08:42:00Z",
    "image_path": "patches/A12_20260424_0842_4ch.png",
    "sensor_seq": "seq/A12_20260424_0842.npy",
    "weather_ctx": [0.12, 34.2],
    "modality_mask": {"image": 1, "sensor": 1, "weather": 1},
    "label": 0.22
  }
  ```
- **Chiến lược mask trong dataset**:
  - Với xác suất `p=0.3`, gán `modality_mask[mod] = 0`
  - Thay tensor tương ứng bằng `zero-vector` cùng shape
  - Concat `mask_flag` vào đầu vào model để network biết modality nào bị thiếu
- **QA**: Phân bố mask đồng đều, không có mẫu nào thiếu cả 3 modality cùng lúc

---

## 🏷️ PHẦN 3: XÂY DỰNG GROUND TRUTH & NHÃN (LABELING STRATEGY)

### 3.1. Công thức bán tổng hợp (Semi-Synthetic Expert-Aligned)
Vì Phase 1 chưa có nhãn thực địa, ta xây dựng hàm ánh xạ đa biến → stress probability `[0,1]`:

```python
def compute_stress_label(soil_moisture, ndvi, rain_3h, air_temp, humidity):
    # Ngưỡng nông học lúa (IRRI/FAO)
    sm_deficit = max(0, (35.0 - soil_moisture) / 35.0)  # FC ~35%
    ndvi_drop  = max(0, (0.65 - ndvi) / 0.65)           # Healthy NDVI ~0.65
    heat_stress = max(0, (air_temp - 32.0) / 10.0)
    rain_relief = min(1.0, rain_3h / 15.0)              # Mưa >15mm giảm stress
    
    # Tổ hợp trọng số chuyên gia
    raw_score = 0.45*sm_deficit + 0.30*ndvi_drop + 0.15*heat_stress - 0.20*rain_relief
    raw_score = np.clip(raw_score, 0.0, 1.0)
    
    # Sigmoid mapping + noise thực địa
    prob = 1 / (1 + np.exp(-8*(raw_score - 0.5)))
    prob += np.random.normal(0, 0.03)  # ±3% noise
    return np.clip(prob, 0.0, 1.0)
```

### 3.2. Cân bằng phân bố lớp (60% Healthy / 40% Stressed)
- **Healthy**: `label < 0.35`
- **Stressed**: `label ≥ 0.35`
- **Điều chỉnh**: Nếu tỷ lệ lệch >65/35, điều chỉnh ngưỡng sampling hoặc thêm `importance sampling` khi tạo dataset.
- **QA**: Kiểm tra histogram label, đảm bảo phân bố liên tục, không đứt gãy nhân tạo.

---

## 📦 PHẦN 4: ĐÓNG GÓI DATASET & VERSIONING

### 4.1. Cấu trúc thư mục
```
data/
├── raw/
│   ├── sentinel2_patches/      # 4-channel PNG/GeoTIFF
│   ├── plantvillage_rice/      # Leaf images
│   ├── sensor_mock.csv
│   └── weather_mock.csv
├── aligned/
│   ├── features/               # sensor_seq.npy, weather_ctx.npy
│   ├── masks/                  # modality_mask.json
│   └── labels.csv              # sample_id, zone, t0, stress_prob
├── splits/
│   ├── train_zones_weeks.csv
│   ├── val_zones_weeks.csv
│   └── test_zones_weeks.csv
└── dvc/
    ├── data.dvc
    └── .dvc/config             # Remote: MinIO / GDrive
```

### 4.2. Spatial-Temporal Split (Chống Leakage)
| Tập | Zones | Weeks | Tỷ lệ | Ghi chú |
|-----|-------|-------|-------|---------|
| Train | A12, B07, C19 | 1–3 | 70% | Học quan hệ đa phương thức |
| Val   | D03           | 4   | 15% | Tuning hyperparams, early stopping |
| Test  | E24, F15      | 5–6 | 15% | Đánh giá tổng quát hóa thực địa |

### 4.3. Versioning & Reproducibility
- **DVC** theo dõi `raw/`, `aligned/`, `splits/`
- **Metadata card** (`dataset_card.md`): nguồn, công thức label, split strategy, missing modality rate, checksum
- **Export**: `parquet` cho tabular, `png/npy` cho tensor, `json` cho mask

---

## 🗓️ PHẦN 5: PHÂN BỔ TÁC VỤ & LỘ TRÌNH (ĐỒNG BỘ 14 NGÀY)

| Ngày | Tác vụ dữ liệu | Đầu ra | Phụ thuộc | Owner |
|------|----------------|--------|-----------|-------|
| 1 | Setup GEE, tải Sentinel-2 band B2,B3,B4,B8, cloud mask | `raw/sentinel2_patches/` | - | AI/DA |
| 2 | Tải PlantVillage rice, generate sensor/weather mock theo IRRI | `raw/sensor_mock.csv`, `weather_mock.csv` | - | AI/DA |
| 3 | Implement Kriging spatial + 1h resample + 48h windowing | `aligned/features/` | Ngày 1-2 | AI |
| 4 | Xây dựng hàm label bán tổng hợp, cân bằng 60/40, tạo mask p=0.3 | `aligned/labels.csv`, `masks/` | Ngày 3 | AI |
| 5 | Implement spatial-temporal split, đóng gói DVC, checksum | `splits/`, `data.dvc` | Ngày 4 | AI/BE |
| 6 | Viết `MultimodalDataset` PyTorch, test loader, visualize sample | `data/dataset.py`, notebook QA | Ngày 5 | AI |
| 7–8 | Train baseline (Image-only, Sensor-only) để validate data quality | Baseline metrics, confusion | Ngày 6 | AI |
| 9–10 | Train Cross-Attention Fusion, ablation missing modality | Model checkpoint, ablation table | Ngày 7-8 | AI |
| 11–12 | Export ONNX, latency test, tích hợp BE `/v1/predict` | `model.onnx`, API contract | Ngày 10 | AI/BE |
| 13–14 | Final eval, calibration plot, dataset card, paper tables | `results/`, `dataset_card.md` | Ngày 12 | AI |

---

## ✅ PHẦN 6: QA/QC & TIÊU CHÍ NGHIỆM THU DỮ LIỆU

| Hạng mục | Tiêu chí đạt | Phương pháp kiểm tra |
|----------|--------------|----------------------|
| **Đồng bộ thời gian** | Sai lệch timestamp ảnh ↔ sensor ≤ 5 phút | `assert abs(t_img - t_sen.max()) < 300` |
| **Nội suy không gian** | RMSE Kriging < 15%, không artifact biên | Cross-validation điểm sensor, plot heatmap |
| **Phân bố nhãn** | 60±5% Healthy / 40±5% Stressed, phân bố liên tục | Histogram, KDE plot, Shapiro-Wilk test |
| **Missing Modality** | Tỷ lệ mask đúng p=0.3, không mẫu nào thiếu 3/3 | `assert mask.sum(axis=1) >= 1` |
| **Không leakage** | Zone/week train ∩ val ∩ test = ∅ | Set intersection check, spatial plot |
| **Tensor shape** | Image: `[B,4,224,224]`, Sensor: `[B,48,8]`, Weather: `[B,2]` | `torch.utils.data.DataLoader` dry-run |
| **Reproducibility** | DVC pull → checksum match, seed cố định | `dvc repro`, `sha256sum` |

---

## 🛠️ PHẦN 7: CÔNG CỤ & CODE SCAFFOLD

### 7.1. Stack xử lý dữ liệu
| Tác vụ | Thư viện | Lý do |
|--------|----------|-------|
| GEE & Remote Sensing | `earthengine-api`, `rasterio`, `geemap` | Tải Sentinel-2, tính NDVI, crop zone |
| Spatial Interpolation | `pykrige`, `scikit-gstat` | Ordinary Kriging, semivariogram fit |
| Time-Series | `pandas`, `xarray`, `numpy` | Resample, windowing, normalization |
| Dataset Versioning | `DVC`, `MinIO` | Reproducibility, remote storage |
| PyTorch Loader | `torch`, `torchvision`, `albumentations` | MultimodalDataset, augmentation, masking |

### 7.2. PyTorch Dataset Skeleton (Ánh xạ trực tiếp vào model)
```python
# data/dataset.py
import torch
import numpy as np
import pandas as pd
from pathlib import Path
from torchvision import transforms

class MultimodalWaterStressDataset(torch.utils.data.Dataset):
    def __init__(self, split_csv: str, data_dir: str, modality_dropout_p: float = 0.3, training: bool = True):
        self.meta = pd.read_csv(split_csv)
        self.data_dir = Path(data_dir)
        self.p = modality_dropout_p
        self.training = training
        
        self.img_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406, 0.5], 
                                 std=[0.229, 0.224, 0.225, 0.25])
        ])

    def __len__(self): return len(self.meta)

    def __getitem__(self, idx):
        row = self.meta.iloc[idx]
        
        # Load image (4ch: RGB+NIR)
        img = np.load(self.data_dir / row.image_path)  # [224,224,4]
        img = self.img_transform(img)                  # [4,224,224]
        
        # Load sensor sequence & weather
        sensor = np.load(self.data_dir / row.sensor_seq)  # [48,8]
        weather = np.array(row.weather_ctx, dtype=np.float32)  # [2]
        
        label = torch.tensor(row.stress_prob, dtype=torch.float32)
        
        # Modality Dropout (training only)
        mask_img = mask_sen = mask_wth = 1.0
        if self.training:
            mask_img = float(torch.bernoulli(torch.tensor(1 - self.p)))
            mask_sen = float(torch.bernoulli(torch.tensor(1 - self.p)))
            mask_wth = float(torch.bernoulli(torch.tensor(1 - self.p)))
            
            if mask_img == 0: img = torch.zeros_like(img)
            if mask_sen == 0: sensor = np.zeros_like(sensor)
            if mask_wth == 0: weather = np.zeros_like(weather)
                
        return {
            "image": img,
            "sensor": torch.tensor(sensor, dtype=torch.float32),
            "weather": torch.tensor(weather, dtype=torch.float32),
            "mask": torch.tensor([mask_img, mask_sen, mask_wth], dtype=torch.float32),
            "label": label,
            "sample_id": row.sample_id
        }
```

---

## 🎯 KẾT LUẬN & NEXT STEP

Kế hoạch dữ liệu này:
- ✅ **Khép kín** từ thu thập → alignment → labeling → splitting → PyTorch loader
- ✅ **Chống leakage** bằng spatial-temporal split, kiểm chứng bằng QA script
- ✅ **Tương thích 100%** với kiến trúc DL đã chốt (4ch image, T=48, 8 vars, p=0.3 dropout, regression [0,1])
- ✅ **Sẵn sàng research** với DVC versioning, dataset card, ablation-ready structure
- ✅ **Khả thi trong 14 ngày** nhờ chiến lược bán tổng hợp có cơ sở nông học + tự động hóa pipeline

**Trong 24h tới, tôi có thể bàn giao ngay:**
1. Script GEE tải Sentinel-2 + tính NDVI + crop zone
2. Module `kriging_aligner.py` + `temporal_windower.py`
3. Hàm `compute_stress_label()` + script cân bằng phân bố 60/40
4. `dataset_card.md` chuẩn IEEE/AgML
5. Notebook QA visualize alignment, label distribution, mask simulation

Jun chỉ cần reply `XÁC NHẬN DATA` hoặc yêu cầu ưu tiên module nào trước, tôi sẽ export code + script tương ứng ngay lập tức. Pipeline dữ liệu này sẽ là nền tảng vững chắc để model hội tụ nhanh, ablation rõ ràng, và paper có độ tin cậy cao. 🌱📊