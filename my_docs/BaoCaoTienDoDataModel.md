# Báo cáo tiến độ Data + Model + Backend

## 1. Tóm tắt trạng thái hiện tại

### Data pipeline

Đã hoàn thành các mốc chính:

- tải raw data theo hướng **GEE-free**
- mở rộng historical window cho Sentinel-2 + Open-Meteo
- build được dataset thật-derived vào `data/processed_real/`
- integrity check pass trên dataset train hiện dùng
- train smoke test chạy được end-to-end trên dữ liệu thật-derived

### Training stack

Đã chỉnh sửa xong train stack để khớp với continuous proxy labels:

- default `data_dir` chuyển sang `data/processed_real/`
- loader có fail-fast validation cho manifest/tensor/source status
- objective đổi sang **proxy regression**
- metric chính đổi sang continuous metrics: `loss`, `mae`, `rmse`
- binary metrics giữ lại làm diagnostic phụ
- thêm evaluation cho `test_manifest.csv`
- test suite ML pass toàn bộ

### Backend

Đã khảo sát xong backend. Kết luận:

- có skeleton API khá đầy đủ
- có ONNX wrapper
- có decision engine
- nhưng **AI serving thật vẫn chưa wire vào `/internal/predict`**
- backend hiện chưa có lớp feature/tensor assembly từ `zone_id + timestamp`

---

## 2. Data hiện có để training đến mức nào?

### Dataset training hiện dùng

Canonical training root hiện tại:

```text
data/processed_real/
```

Manifest chính:

```text
data/processed_real/sample_manifest.csv
```

Các split:

```text
data/processed_real/train_manifest.csv
data/processed_real/val_manifest.csv
data/processed_real/test_manifest.csv
```

### Chất lượng hiện tại

**Kết luận:** đủ để chạy baseline end-to-end thật-derived, nhưng chưa đủ để claim production-grade hoặc field-ready.

Lý do:

- label vẫn là **continuous proxy label** `[0,1]`
- zone vẫn là **synthetic validation polygon**
- `sensor_seq` vẫn là **weather-derived proxy sequence**
- chưa có field boundary thật
- chưa có ground-truth label từ hiện trường

### Những gì đã GO

Có thể làm tiếp:

- DataLoader thật
- training loop thật
- checkpoint thật
- evaluation train/val/test thật
- ONNX export pipeline
- backend model serving integration
- demo end-to-end

### Những gì vẫn NO-GO

Chưa nên claim:

- field-ready agronomic accuracy
- production deployment thực chiến
- model scientific benchmark mạnh
- ground-truth stress prediction
- sensor thật ngoài ruộng

---

## 3. Training stack đã sửa gì?

### 3.1 Config

Đã đổi default training root:

- `ml_pipeline/configs/train.yaml`
  - `data_dir: data/processed_real/`
  - `checkpoint_metric: rmse`
  - `evaluate_test_manifest: true`
  - `validate_checksums: false`

### 3.2 Loss / Objective

Đã đổi objective sang continuous proxy regression:

- `ml_pipeline/training/losses.py`
  - `ProxyRegressionLoss`
- `ml_pipeline/configs/model.yaml`
  - `loss: proxy_mse`

Hiện tại model học theo hướng:

```text
sigmoid(logits) -> proxy stress score
loss = MSE(probability, proxy_label)
```

Thay vì ép semantics kiểu binary classification như trước.

### 3.3 Metrics

Đã chuyển metric chính sang continuous:

- `mae`
- `rmse`
- `mse`

Binary metrics giữ lại chỉ để chẩn đoán:

- `binary_f1`
- `binary_auc_roc`
- `binary_auc_pr`

### 3.4 Loader validation

`ManifestDataset` giờ kiểm tra fail-fast:

- required columns
- `source_status == PASS`
- label nằm trong `[0,1]`
- modality mask hợp lệ
- tensor shape/dtype đúng contract
- checksum validation hỗ trợ cho:
  - `image_checksum`
  - `sensor_seq_checksum`
  - `weather_ctx_checksum`

### 3.5 Test evaluation

Training flow giờ:

1. train trên `train_manifest.csv`
2. chọn checkpoint tốt nhất bằng metric continuous trên `val_manifest.csv`
3. evaluate `test_manifest.csv` bằng **best checkpoint**

### 3.6 Test coverage

Đã thêm/điều chỉnh tests:

- `tests/ml/test_metrics.py`
- `tests/ml/test_builders.py`
- `tests/ml/test_train_skeleton.py`
- `tests/ml/test_loss_one_step.py`

Kết quả verify cuối cùng:

```text
71 passed
```

---

## 4. Input / Output model hiện tại

### Input

Model hiện nhận 4 input:

| Input | Shape | Ý nghĩa |
|---|---:|---|
| `image` | `[B, 4, 224, 224]` | Sentinel-2 Blue, Green, Red, NIR |
| `sensor_seq` | `[B, 48, 8]` | weather-derived proxy sequence |
| `weather_ctx` | `[B, 6]` | ngữ cảnh thời tiết tổng hợp |
| `modality_mask` | `[B, 3]` | cờ tồn tại image/sensor/weather |

### Output

Model trả về:

| Output | Shape | Ý nghĩa |
|---|---:|---|
| `logits` | `[B, 1]` | raw score |
| `attention_weights` | `[B, N]` | trọng số attention |

Sau post-process:

```python
stress_prob = sigmoid(logits)
```

`stress_prob` là **proxy stress score**, không phải ground-truth disease classifier.

---

## 5. Backend khảo sát: trạng thái thực tế

### Đã có

API gateway đã có route:

- `/v1/healthz`
- `/v1/readyz`
- `/v1/predict`
- `/v1/recommend`
- `/v1/telemetry`
- `/v1/commands`
- `/v1/zones/{zone_id}/status`
- `/ws/updates`

Các khối đã tồn tại:

- `backend/api_gateway/`
- `backend/ai_serving/`
- `backend/decision_engine/`
- `backend/ingestion_service/`
- `backend/core/schemas.py`
- `backend/ai_serving/onnx_wrapper.py`

### Chưa có / còn block

Blocker backend lớn nhất hiện tại:

1. `backend/ai_serving/main.py`
   - `/internal/predict` vẫn đang trả mock
   - chưa load ONNX model thật
   - chưa gọi `OnnxInferenceWrapper`

2. `PredictRequest`
   - mới có `zone_id`, `timestamp`, `model_version`
   - chưa có lớp assemble input thật từ backend storage/data layer

3. Chưa có startup model loading
   - chưa load model artifact
   - chưa load calibrator artifact
   - chưa có readiness check “model loaded”

4. `readyz` còn nông
   - mới báo dependency configured
   - chưa verify service/model/backend dependency thật

5. Auth/security chưa được wire vào endpoint

6. Có nguy cơ inflate uncertainty nhiều lần giữa:
   - ONNX wrapper
   - post-processor
   - decision engine

### Kết luận backend

**Backend chưa sẵn sàng production**, nhưng đã có skeleton đủ tốt để sang phase implement model serving thật.

---

## 6. Kết quả smoke training gần nhất

Smoke train gần nhất trên `data/processed_real` chạy pass.

Ví dụ metric log gần nhất:

```text
train_loss ≈ 0.01596
val_loss   ≈ 0.01381
val_mae    ≈ 0.12967
val_rmse   ≈ 0.12986
```

Lưu ý:

- metric này dùng dataset proxy-derived nhỏ
- có giá trị để validate pipeline
- chưa đủ để kết luận model quality thực chiến

---

## 7. Giới hạn còn tồn tại

### Data side

- dataset thật-derived vẫn còn hạn chế chất lượng
- proxy label chưa phải ground truth
- zone polygon chưa phải field boundary thật
- sensor sequence chưa phải field telemetry thật
- sample count vẫn cần tăng thêm nếu muốn train nghiêm túc hơn

### Backend side

- serving thật chưa wire
- inference request chưa gắn với feature/tensor assembly thật
- chưa có readiness check đầy đủ
- chưa có auth + internal service hardening

---

## 8. Hướng làm tiếp hợp lý cho ngày mai

### Ưu tiên 1: Backend AI serving thật

Làm theo thứ tự:

1. wire `backend/ai_serving/main.py` dùng ONNX thật
2. thêm startup load model + calibrator
3. thêm `/healthz` + `/readyz` cho ai-serving
4. xây input assembly từ `zone_id + timestamp`
5. nối `/v1/predict` chạy end-to-end thật
6. rà lại uncertainty inflation giữa các layer

### Ưu tiên 2: Data quality nâng cấp sau đó

Sau khi backend demo được inference thật, quay lại tăng chất lượng data:

- tăng sample count
- crop theo field boundary thật
- sensor/telemetry thật
- ground-truth label nếu có

---

## 9. Kết luận cuối ngày

- ML training stack: **đã chỉnh xong và verify pass**
- real-derived dataset path: **đã dùng được**
- backend survey: **đã rõ blocker và sẵn sàng sang phase implement**
- hướng ngày mai hợp lý nhất: **xử lý backend AI serving thật**

### Todo nhanh cho ngày mai

1. Resume từ Backend: wire `backend/ai_serving/main.py` load ONNX thật và gọi `OnnxInferenceWrapper`.
2. Sau đó kiểm tra lại `data/processed_real/` và rebuild dataset nếu cần trước khi train baseline dài hơn.

Nói ngắn:

> Data + training pipeline đã đủ ổn để rời sang Backend. Backend hiện có khung tốt nhưng inference thật vẫn chưa được wire vào service.
