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
| ONNX export | PASS |
| ONNX path | `artifacts/model.onnx` |
| ONNX size | 44.84 MB |
| ONNX verify | PASS for batch sizes 1 / 2 / 4 |
| Average latency | 150.70 ms |
| Notes | Training completed successfully on CUDA. Export ONNX completed and verification passed. Local archive import on 2026-05-08 restored `checkpoints/colab_train/best.pt` and `logs/colab_train/training_metrics.csv`, and CSV metrics matched recorded summary. Metrics are prototype-only because dataset has 13 samples. `binary_auc_roc` is `nan` due tiny/single-class split behavior. Hugging Face warning only affects rate limits, not training success. |

### Final artifact summary

- Training: PASS
- Best checkpoint: `checkpoints/colab_train/best.pt`
- ONNX export: PASS
- ONNX verify batch 1/2/4: PASS
- ONNX artifact: `artifacts/model.onnx`
- Model size: 44.84 MB
- Average latency: 150.70 ms
- Final test RMSE: 0.01707045869169988
- Final test MAE: 0.015334740281105042

### Accuracy interpretation for reporting

Có 2 cách đọc kết quả model hiện tại.

1. Theo bài toán regression / proxy score:
   - Metric chính nên dùng là `MAE`, `RMSE`, `loss`
   - `test_mae = 0.015334740281105042`
   - `test_rmse = 0.01707045869169988`
   - `test_loss = 4.725955659523606e-05`
   - Diễn giải thực dụng: sai số trung bình khoảng `0.0153` trên thang `[0,1]`, phù hợp để báo cáo demo/prototype

2. Nếu ép sang binary classification để báo cáo demo:
   - `binary_accuracy = 1.0`
   - `binary_precision = 1.0`
   - `binary_recall = 1.0`
   - `binary_f1 = 1.0`

Cảnh báo khi trình bày:
- test set hiện rất nhỏ
- `binary_auc_roc = nan`
- không được diễn giải thành model production đạt `100%` accuracy
- kết quả hiện tại chỉ nên hiểu là model fit được tập demo nhỏ hiện có

Kết luận khuyến nghị:
- nếu cần một câu ngắn cho demo: có thể nói `binary accuracy = 100% trên test set nhỏ hiện tại`
- nếu cần metric đáng tin hơn: dùng `MAE = 0.0153`, `RMSE = 0.0171`
- không claim production accuracy

### Step 8 command log

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

### Extracted `training_metrics.csv` confirmation

```text
epoch,train_loss,train_grad_norm,val_loss,val_mae,val_rmse,val_binary_f1,val_binary_auc_roc,lr,test_loss,test_mae,test_rmse,test_binary_f1,test_binary_auc_roc
1,0.015390126034617424,0.49185365438461304,0.011984928511083126,0.12161388993263245,0.12180703190532943,1.0,nan,5.417662350913719e-05,,,,,
2,0.01500693242996931,0.41280534863471985,0.006483095698058605,0.0926261842250824,0.09284804004893353,1.0,nan,0.000156,,,,,
3,0.008760030381381512,0.3876180350780487,0.0002646384236868471,0.027675390243530273,0.02832965347375468,1.0,nan,0.0002578233764908628,,,,,
4,0.00137656822334975,0.10399805009365082,0.0031657088547945023,0.04342415928840637,0.044230744791487614,1.0,nan,0.0003,,,,,
5,0.004846099764108658,0.19105328619480133,0.006633848883211613,0.0688062310218811,0.0692750132555641,1.0,nan,0.0002996346090005435,,,,,
6,0.004726617131382227,0.16213475167751312,0.006865754723548889,0.07028797268867493,0.07066372727398411,1.0,nan,0.00029854021615039427,,,,,
7,0.004568869713693857,0.1531381607055664,0.004708088934421539,0.05601838231086731,0.056450011295374705,1.0,nan,0.00029672215322151037,,,,,
8,0.0022669807076454163,0.12361767888069153,0.002004525624215603,0.0320073664188385,0.03277770095960603,1.0,nan,0.0002941892776337302,,,,,
9,0.0017899391241371632,0.04812272638082504,0.0004333641554694623,0.00748094916343689,0.01035580462396616,1.0,nan,0.00029095392930231375,,,,,
10,0.0004648165195249021,0.026215238496661186,4.0579692722531036e-05,0.01231682300567627,0.014205706745159002,1.0,nan,0.0002870318705191155,,,,,
11,0.0013352412497624755,0.056740064173936844,0.00014186595217324793,0.022530317306518555,0.023541632677269272,1.0,nan,0.0002824422091602833,,,,,
12,0.0012712058378383517,0.10095151513814926,9.870332723949105e-05,0.020378410816192627,0.021391791701152074,1.0,nan,0.00027720730559460617,,,,,
13,0.0025671047624200583,0.0755511075258255,3.052101965295151e-05,0.011720985174179077,0.013260125288683878,1.0,nan,0.00027135266374604547,,,,,
14,0.0031372313387691975,0.02833377942442894,9.174529986921698e-05,0.00588718056678772,0.0072631600523815594,1.0,nan,0.0002649068068411808,,,,,
15,0.0037332214415073395,0.03014860302209854,0.0002041213447228074,0.005637317895889282,0.005743391278167986,1.0,nan,0.00025790113844691745,,,,,
16,0.00416179746389389,0.05024740844964981,0.0003135975857730955,0.005549430847167969,0.00728714395792903,1.0,nan,0.0002503697894754649,,,,,
17,0.0002613345277495682,0.012961788102984428,0.0004333830438554287,0.00792306661605835,0.009704162480283163,1.0,nan,0.00024234945190196354,,,,,
18,0.002152720233425498,0.017302701249718666,0.0005242080078460276,0.010052263736724854,0.011514725463003922,1.0,nan,0.00023387920000486994,,,,,
19,0.0010035005398094654,0.03226710483431816,0.0006311265751719475,0.012341856956481934,0.013528748962074592,1.0,nan,0.00022500030000000001,,,,,
20,0.001974714221432805,0.042389560490846634,0.0005646366626024246,0.010992348194122314,0.012227022966726708,1.0,nan,0.00021575600899567354,,,,,
21,0.0022577301133424044,0.032025694847106934,0.0004226560122333467,0.007774800062179565,0.009293538549102077,1.0,nan,0.00020619136424843078,,,,,
22,0.0026477959472686052,0.026018252596259117,0.0003551347181200981,0.00606951117515564,0.00777928338274443,1.0,nan,0.00019635296374604549,,,,,
test_best,,,,,,,,,4.725955659523606e-05,0.015334740281105042,0.01707045869169988,1.0,nan
```

---

## 16. Hướng dẫn cập nhật tiếp

Khi anh gửi thêm list training ở bước 8, tôi sẽ:

1. ghi nhận command train chính thức,
2. cập nhật mục `Training Record Template`,
3. lưu metric/ghi chú vào tài liệu này để thành log training model chuẩn.
