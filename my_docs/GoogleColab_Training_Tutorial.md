# Google Colab Training Tutorial

Owner: Anh Nhat Tu  
Project: AgMultida  
Mode: Google Colab GPU training  
Target: clone code từ `develop`, nạp `data/processed_real`, chạy train, export ONNX, tải checkpoint về

---

## 1. Mục tiêu

Tài liệu này hướng dẫn chạy training model trên Google Colab khi chưa dùng được GPU Droplet.

Mục tiêu thực thi:

1. Tạo Colab notebook mới và bật GPU.
2. Clone repo từ GitHub branch `develop`.
3. Cài dependencies cần cho training.
4. Kiểm tra hoặc upload `data/processed_real`.
5. Chạy integrity check.
6. Chạy smoke train 1 epoch.
7. Chạy training chính.
8. Export ONNX từ best checkpoint.
9. Tải output về local.

Lưu ý quan trọng:

- Data train hiện tại đúng là `data/processed_real`.
- Bộ data hiện tại chỉ có 13 samples, phù hợp smoke/prototype/demo training, chưa đủ để kết luận chất lượng production.
- Nếu repo GitHub không chứa `data/processed_real`, phải upload thủ công từ local hoặc Google Drive.

---

## 2. Chuẩn bị runtime trên Colab

### Bước 1. Tạo notebook mới

Vào Google Colab → New notebook.

### Bước 2. Bật GPU

```text
Runtime → Change runtime type → GPU
```

Ưu tiên:

- T4 GPU
- L4 nếu có
- A100 nếu có

### Bước 3. Kiểm tra GPU

```python
!nvidia-smi
```

---

## 3. Clone repo từ GitHub

```python
!git clone -b develop https://github.com/JimmyNotAvailable/AgMultida.git
%cd AgMultida
```

---

## 4. Cài dependencies

### Cách ưu tiên

```python
!pip install --upgrade pip
!pip install -r deploy/vps/requirements_gpu.txt
```

### Nếu Colab bị conflict Torch/CUDA

Dùng bản cài thủ công nhẹ hơn:

```python
!pip install --upgrade pip
!pip install timm onnx onnxruntime-gpu onnxscript scikit-learn joblib numpy pandas pyyaml pytest fastapi uvicorn pydantic PyJWT httpx rasterio
```

### Kiểm tra PyTorch và GPU

```python
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO GPU")
```

Kỳ vọng:

- `torch.cuda.is_available()` trả về `True`
- Có tên GPU như `Tesla T4`, `L4`, `A100`

---

## 5. Kiểm tra data có sẵn không

```python
!ls -lah data/processed_real
!ls -lah data/processed_real/samples | head
```

Phải thấy ít nhất:

- `sample_manifest.csv`
- `train_manifest.csv`
- `val_manifest.csv`
- `test_manifest.csv`

Nếu đủ file trên, đi tiếp.

Nếu thiếu `data/processed_real`, làm bước upload ở dưới.

---

## 6. Upload data nếu repo không có data

### Cách A. Nén data từ local rồi upload trực tiếp lên Colab

Trên máy local:

```bash
tar -czf processed_real.tar.gz data/processed_real
```

Upload file `processed_real.tar.gz` lên Colab bằng panel Files.

Giải nén trên Colab:

```python
!tar -xzf processed_real.tar.gz
!ls -lah data/processed_real
```

### Cách B. Lấy từ Google Drive

Mount Drive:

```python
from google.colab import drive
drive.mount('/content/drive')
```

Copy file nén từ Drive:

```python
!cp /content/drive/MyDrive/processed_real.tar.gz .
!tar -xzf processed_real.tar.gz
!ls -lah data/processed_real
```

---

## 7. Chạy integrity check

```python
!python scripts/check_data_integrity.py --data-dir data/processed_real
```

Kỳ vọng hiện tại:

```text
"status": "PASS"
"total_samples": 13
"valid_arrays": 39
```

Nếu bước này fail thì dừng ngay và sửa data trước khi train.

---

## 8. Chạy smoke train trước

Mục tiêu: kiểm tra pipeline train end-to-end có chạy được trước khi chạy dài hơn.

```python
!PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 1 \
  --num-workers 2 \
  --checkpoint-dir checkpoints/colab_smoke \
  --log-dir logs/colab_smoke \
  --amp
```

Nếu pass, kiểm tra output:

```python
!ls -lah checkpoints/colab_smoke
!cat logs/colab_smoke/training_metrics.csv
```

Nếu Colab báo lỗi worker hoặc RAM, giảm về:

```text
--num-workers 0
```

---

## 9. Chạy training chính

Vì data hiện tại nhỏ, nên training này chủ yếu để:

- verify pipeline trên GPU
- tạo checkpoint dùng cho demo/export/inference
- chuẩn bị cho bước scale data sau này

### Lệnh mặc định

```python
!PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 50 \
  --num-workers 2 \
  --checkpoint-dir checkpoints/colab_train \
  --log-dir logs/colab_train \
  --amp
```

### Nếu Colab thiếu RAM hoặc worker crash

Dùng:

```python
!PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 20 \
  --num-workers 0 \
  --checkpoint-dir checkpoints/colab_train \
  --log-dir logs/colab_train \
  --amp
```

---

## 10. Xem metrics sau training

### Cách 1. Dùng pandas

```python
import pandas as pd

metrics = pd.read_csv("logs/colab_train/training_metrics.csv")
metrics.tail()
```

### Cách 2. In raw CSV

```python
!cat logs/colab_train/training_metrics.csv
```

---

## 11. Export ONNX từ best checkpoint

```python
!mkdir -p artifacts
!PYTHONPATH=. python ml_pipeline/export/export_onnx.py \
  --checkpoint checkpoints/colab_train/best.pt \
  --output artifacts/model.onnx \
  --allow-unsafe-checkpoint-load
```

Kiểm tra file ONNX:

```python
!ls -lh artifacts/model.onnx
```

---

## 12. Tải checkpoint và ONNX về local

Nén output:

```python
!tar -czf colab_training_outputs.tar.gz checkpoints/colab_train logs/colab_train artifacts/model.onnx
```

Download:

```python
from google.colab import files
files.download("colab_training_outputs.tar.gz")
```

---

## 13. Bản copy-paste tối giản

Chạy lần lượt từng cell dưới đây.

### Cell 1

```python
!nvidia-smi
```

### Cell 2

```python
!git clone -b develop https://github.com/JimmyNotAvailable/AgMultida.git
%cd AgMultida
```

### Cell 3

```python
!pip install --upgrade pip
!pip install timm onnx onnxruntime-gpu onnxscript scikit-learn joblib numpy pandas pyyaml pytest fastapi uvicorn pydantic PyJWT httpx rasterio
```

### Cell 4

```python
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO GPU")
```

### Cell 5

```python
!python scripts/check_data_integrity.py --data-dir data/processed_real
```

### Cell 6

```python
!PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 1 \
  --num-workers 2 \
  --checkpoint-dir checkpoints/colab_smoke \
  --log-dir logs/colab_smoke \
  --amp
```

### Cell 7

```python
!PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 50 \
  --num-workers 2 \
  --checkpoint-dir checkpoints/colab_train \
  --log-dir logs/colab_train \
  --amp
```

### Cell 8

```python
!mkdir -p artifacts
!PYTHONPATH=. python ml_pipeline/export/export_onnx.py \
  --checkpoint checkpoints/colab_train/best.pt \
  --output artifacts/model.onnx \
  --allow-unsafe-checkpoint-load
```

### Cell 9

```python
!tar -czf colab_training_outputs.tar.gz checkpoints/colab_train logs/colab_train artifacts/model.onnx
from google.colab import files
files.download("colab_training_outputs.tar.gz")
```

---

## 14. Ghi chú lỗi thường gặp

### 14.1. Không thấy `data/processed_real`

Nguyên nhân:
- repo không chứa data lớn
- chưa upload `processed_real.tar.gz`

Cách xử lý:

```bash
tar -czf processed_real.tar.gz data/processed_real
```

Rồi upload lên Colab và giải nén:

```python
!tar -xzf processed_real.tar.gz
```

### 14.2. Lỗi worker / RAM

Giảm:

```text
--num-workers 0
```

### 14.3. Lỗi Torch/CUDA dependency

Bỏ `requirements_gpu.txt`, cài manual bằng nhóm package nhẹ ở mục 4.

### 14.4. Session Colab bị ngắt

Nếu checkpoint đã tạo, có thể resume bằng lệnh riêng sau khi xác nhận path checkpoint.

---

## 15. Mẫu ghi nhận training model

Mục này để ghi log training thật sau khi anh chốt cấu hình bước 8.

### Training Record Template

| Field | Value |
| --- | --- |
| Date | 2026-05-08 |
| Runtime | Google Colab |
| GPU | CUDA available, exact GPU name not captured in pasted log |
| Branch | `develop` |
| Data dir | `data/processed_real` |
| Sample count | 13 |
| Integrity check | PASS before training |
| Smoke train | PASS before main run |
| Main training command | See Step 8 command log |
| Epochs | Requested 50, early stopped at epoch 22 |
| Num workers | 2 |
| AMP | Enabled |
| Best checkpoint | `checkpoints/colab_train/best.pt` |
| Best epoch | 15 |
| Final test RMSE | 0.01707045869169988 |
| Final test MAE | 0.015334740281105042 |
| Final test loss | 4.725955659523606e-05 |
| ONNX export | Pending |
| Notes | Training completed successfully on CUDA. Metrics are prototype-only because dataset has 13 samples. `binary_auc_roc` is `nan` due tiny/single-class split behavior. Hugging Face warning only affects rate limits, not training success. |

### Step 8 command log

```bash
PYTHONPATH=. python -m ml_pipeline.training.train \
  --data-dir data/processed_real \
  --max-epochs 50 \
  --num-workers 2 \
  --checkpoint-dir checkpoints/colab_train \
  --log-dir logs/colab_train \
  --amp
```

### Step 8 result log

```text
Device: cuda
Requested epochs: 50
Early stopping: triggered after epoch 22
Best checkpoint: checkpoints/colab_train/best.pt
Best epoch loaded for test: 15

Best validation checkpoint moments:
- Epoch 3: val_rmse=0.02832965347375468
- Epoch 9: val_rmse=0.01035580462396616
- Epoch 14: val_rmse=0.0072631600523815594
- Epoch 15: val_rmse=0.005743391278167986

Final test metrics from best checkpoint:
mae=0.015334740281105042
rmse=0.01707045869169988
mse=0.000291400559945032
binary_accuracy=1.0
binary_precision=1.0
binary_recall=1.0
binary_f1=1.0
binary_auc_roc=nan
binary_auc_pr=1.0
loss=4.725955659523606e-05
```

---

## 16. Hướng dẫn cập nhật tiếp

Khi anh gửi thêm list training ở bước 8, tôi sẽ:

1. ghi nhận command train chính thức,
2. cập nhật mục `Training Record Template`,
3. lưu metric/ghi chú vào tài liệu này để thành log training model chuẩn.
