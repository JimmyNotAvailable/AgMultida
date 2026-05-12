# Tổng Hợp Chức Năng Dự Án AgMultida

## 1. Tổng quan kiến trúc

Dự án hiện có các khối chính:

| Khối | Vai trò | File chính |
|---|---|---|
| Frontend | UI website, dashboard, admin | `frontend/src/app/router.tsx` |
| API Gateway | API công khai cho frontend gọi | `backend/api_gateway/main.py` |
| AI Serving | Chạy model ML/ONNX inference | `backend/ai_serving/main.py` |
| Decision Engine | Sinh khuyến nghị tưới | `backend/decision_engine/main.py` |
| Ingestion Service | Nhận telemetry/sensor data | `backend/ingestion_service/main.py` |
| ML Pipeline | Dataset, train, export ONNX | `ml_pipeline/**` |
| Data Pipeline | Thu thập/xử lý Sentinel, weather, labels | `scripts/**`, `metadata/**` |

Backend có 2 mode:

| Mode | Ý nghĩa |
|---|---|
| `GATEWAY_MODE=stub` | Gateway trả dữ liệu giả/demo qua stub client |
| `GATEWAY_MODE=live` | Gateway gọi AI serving, ingestion, decision thật |

---

## 2. Frontend routes hiện có

File route chính: `frontend/src/app/router.tsx`

| Route | Page | Mục đích |
|---|---|---|
| `/` | `WebsitePage` | Landing page giới thiệu hệ thống |
| `/dashboard` | `DashboardPage` | Dashboard vận hành chính |
| `/admin` | `AdminPage` | Trang nội bộ/admin, bị guard bằng env/token |

---

## 3. Chức năng Landing Page

File: `frontend/src/features/website/pages/WebsitePage.tsx`

### FE xử lý

Landing page giới thiệu AgMultida:

- Mô tả hệ thống AI nông nghiệp.
- Mô tả pipeline:
  - dữ liệu vệ tinh
  - sensor
  - weather
  - model prediction
  - irrigation recommendation
- Có CTA mở dashboard:
  - `Access Dashboard`
  - `Open Full Dashboard`
- Điều hướng sang `/dashboard`.

### BE/API liên quan

Landing page chủ yếu tĩnh. Không thấy API call chính trong flow này.

---

## 4. Chức năng Dashboard chính

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

Đây là màn hình chính người dùng dùng để vận hành.

### FE xử lý

Dashboard làm các việc:

1. Chọn zone.
2. Đồng bộ zone vào URL query param: `?zone=A01`.
3. Hiển thị bản đồ vùng.
4. Hiển thị ảnh vệ tinh RGB/NDVI.
5. Hiển thị timeline ảnh.
6. Hiển thị trạng thái vùng.
7. Hiển thị alerts.
8. Chạy prediction.
9. Chạy recommendation.
10. Confirm irrigation command nếu đủ tin cậy.

### Component chính

| Component | File | Vai trò |
|---|---|---|
| `ZoneMap` | `frontend/src/components/dashboard/ZoneMap.tsx` | Bản đồ MapLibre, chọn zone, overlay ảnh |
| `ZoneImageryPanel` | `frontend/src/components/dashboard/ZoneImageryPanel.tsx` | Xem ảnh RGB/NDVI mới nhất |
| `ImageryTimeline` | `frontend/src/components/dashboard/ImageryTimeline.tsx` | Danh sách ảnh theo thời gian |
| `DataFusionPanel` | `frontend/src/components/dashboard/DataFusionPanel.tsx` | Hiển thị dữ liệu fusion: soil, rain, cloud, source |
| `ZoneOverlay` | `frontend/src/components/dashboard/ZoneOverlay.tsx` | Panel trạng thái/prediction/recommendation/action |
| `LanguageToggle` | `frontend/src/components/shared/LanguageToggle.tsx` | Đổi ngôn ngữ |
| `ThemeToggle` | `frontend/src/components/shared/ThemeToggle.tsx` | Đổi theme |

---

## 5. API client FE

Frontend gọi backend qua `apiRequest` trong:

- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/index.ts`

Base URL:

```text
VITE_API_BASE_URL
```

Default:

```text
http://localhost:8000
```

### API FE đang dùng

| FE function | Method | API |
|---|---:|---|
| `getHealth` | GET | `/v1/healthz` |
| `getReadiness` | GET | `/v1/readyz` |
| `predict` | POST | `/v1/predict` |
| `recommend` | POST | `/v1/recommend` |
| `createCommand` | POST | `/v1/commands` |
| `getZones` | GET | `/v1/zones` |
| `getZoneStatus` | GET | `/v1/zones/:zoneId/status` |
| `getZoneAlerts` | GET | `/v1/zones/:zoneId/alerts` |
| `getZoneImageryLatest` | GET | `/v1/zones/:zoneId/imagery/latest` |
| `getZoneImageryHistory` | GET | `/v1/zones/:zoneId/imagery/history?limit=...` |

### Auth FE xử lý

File: `frontend/src/lib/api/client.ts`

FE tự attach token cho các path:

```text
/v1/zones...
/v1/predict
/v1/recommend
/v1/telemetry
/v1/commands
```

Token lấy từ file: `frontend/src/lib/auth/token.ts`

Ưu tiên:

1. `VITE_DEV_ACCESS_TOKEN`
2. `localStorage['agmultida.accessToken']`

---

## 6. Fallback/demo data FE

File: `frontend/src/features/dashboard/dashboardData.ts`

Frontend có local fallback khi backend lỗi:

- lỗi không phải `ApiError`
- hoặc `ApiError.status >= 500`

Các function có fallback:

| Function | Fallback |
|---|---|
| `predict` | `buildFallbackPrediction` |
| `recommend` | `buildFallbackDecision` |
| `getZones` | local demo zones |
| `getZoneStatus` | `buildFallbackStatus` |
| `getZoneAlerts` | local alert demo |
| `getZoneImageryLatestSafe` | local imagery demo |
| `getZoneImageryHistorySafe` | local imagery history demo |

Demo trace nhận biết bằng:

```text
trace_id starts with "demo-"
```

UI sẽ hiện thông báo kiểu:

```text
Backend unavailable. Showing local demo result.
```

---

## 7. Chức năng Zone selection

### FE xử lý

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

- Đọc zone từ URL query param.
- Validate với local `zones`.
- Nếu zone không hợp lệ, dùng default zone.
- Chọn zone từ:
  - sidebar/list
  - click polygon trên map

### BE/API liên quan

```http
GET /v1/zones
```

Backend route:

File: `backend/api_gateway/main.py`

```py
list_zones
```

Schema:

File: `backend/core/schemas.py`

```py
ZoneListResponse
ZoneRegistryEntry
```

---

## 8. Chức năng bản đồ vùng

### FE xử lý

File: `frontend/src/components/dashboard/ZoneMap.tsx`

Dùng:

```text
maplibre-gl
```

Chức năng:

- Render polygon zone từ local `zoneMap`.
- Click polygon để chọn zone.
- Highlight zone đang chọn.
- Overlay imagery raster nếu có ảnh.
- Toggle mode:
  - `rgb`
  - `ndvi`

### BE/API liên quan

Map polygon chủ yếu từ FE data/local.

Ảnh overlay lấy từ imagery API:

```http
GET /v1/zones/{zone_id}/imagery/latest
GET /v1/imagery/preview/{scene_id}
```

---

## 9. Chức năng imagery RGB/NDVI

### FE xử lý

Files:

- `frontend/src/components/dashboard/ZoneImageryPanel.tsx`
- `frontend/src/components/dashboard/ImageryTimeline.tsx`
- `frontend/src/components/dashboard/ZoneMap.tsx`

FE hiển thị:

- ảnh RGB
- ảnh NDVI
- cloud cover
- acquisition time
- source
- stale/fresh status
- timeline 10 scene gần nhất

Fields FE dùng:

```ts
rgb_url
ndvi_url
acquisition_time
cloud_cover
source
stale
```

### API liên quan

| API | Mục đích |
|---|---|
| `GET /v1/zones/{zone_id}/imagery/latest` | Lấy scene mới nhất |
| `GET /v1/zones/{zone_id}/imagery/history?limit=10` | Lấy lịch sử scene |
| `GET /v1/imagery/preview/{scene_id}` | Render/serve preview PNG |

### BE xử lý

File: `backend/api_gateway/main.py`

Routes:

```py
zone_imagery_latest
zone_imagery_history
imagery_preview
```

Core imagery logic nằm ở:

```text
backend/core/imagery_proxy.py
```

Backend functions:

```py
get_latest_zone_imagery_for_api
get_zone_imagery_history_for_api
get_scene_for_preview
build_preview_png
```

Schema:

File: `backend/core/schemas.py`

```py
ImagerySummary
ImageryScene
ImagerySceneCollection
```

---

## 10. Chức năng prediction ML

### FE xử lý

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

Khi user chạy prediction:

```ts
predict({
  zone_id,
  timestamp,
  model_version: null
})
```

FE hiển thị output:

```ts
stress_prob
uncertainty
confidence_flag
model_version
latency_ms
explanation
attention_weights
degraded_mode
```

Component hiển thị chính:

```text
ZoneOverlay
```

File:

```text
frontend/src/components/dashboard/ZoneOverlay.tsx
```

### API liên quan

```http
POST /v1/predict
```

Request schema:

File: `backend/core/schemas.py`

```py
PredictRequest
```

Response schema:

```py
PredictResponse
FeatureImportance
ConfidenceFlag
```

### BE Gateway xử lý

File: `backend/api_gateway/main.py`

Route:

```py
predict
```

Flow:

```text
POST /v1/predict
-> api_gateway.main.predict
-> request.app.state.ai_client.predict(req)
```

Nếu `stub`:

```text
StubAIClient.predict
```

Nếu `live`:

```text
LiveAIClient.predict
-> POST /internal/predict
-> ai_serving.main.internal_predict
```

### AI Serving xử lý

File: `backend/ai_serving/main.py`

Routes:

| API | Mục đích |
|---|---|
| `GET /healthz` | health nội bộ |
| `GET /public-healthz` | health public |
| `GET /readyz` | readiness, cần internal key |
| `POST /internal/predict` | chạy inference, cần internal key |

Core class:

```py
ManifestSampleStore
```

Nó load manifest từ:

```text
MANIFEST_PATH
```

Required columns:

```text
sample_id
zone_id
timestamp_utc
image_path
sensor_seq_path
weather_ctx_path
modality_mask
source_status
```

Tensor shapes:

```text
image: (4, 224, 224)
sensor_seq: (48, 8)
weather_ctx: (6,)
modality_mask: (3,)
```

Inference flow:

```text
ManifestSampleStore.find_latest_sample
-> ManifestSampleStore.assemble_inputs
-> AIInferencePipeline.predict
-> OnnxInferenceWrapper.predict
-> PostProcessor.process
-> explain_attention
-> PredictResponse
```

### ONNX wrapper

File: `backend/ai_serving/onnx_wrapper.py`

Class:

```py
OnnxInferenceWrapper
```

Chức năng:

- chạy ONNX Runtime
- MC Dropout loop
- default `DEFAULT_MC_PASSES = 10`
- timeout default `DEFAULT_TIMEOUT_MS = 500`
- nếu timeout/failure thì fallback single pass

Output:

```py
InferenceResult
```

Fields:

```py
logits_mean
prob_mean
uncertainty
attention_weights
degraded_mode
passes_completed
latency_ms
```

### Post processing ML

File: `ai_system/post_processor.py`

Class:

```py
PostProcessor
```

Xử lý:

- check uncertainty non-negative
- detect missing modality từ `modality_mask < 1.0`
- degraded mode tăng uncertainty x `1.3`
- calibrate probability bằng `StressCalibrator`
- EMA smoothing theo zone
- gắn confidence flag

Confidence rule:

```text
uncertainty > 0.30 -> low
uncertainty > 0.15 -> medium
else -> high
```

### Calibration

File: `ai_system/calibration.py`

Class:

```py
StressCalibrator
```

Chức năng:

- pass-through nếu chưa fitted
- optional `sklearn.isotonic.IsotonicRegression`
- support:
  - `fit`
  - `predict`
  - `save`
  - `load`

### XAI/explanation

File: `ai_system/xai_explainer.py`

Function:

```py
explain_attention
```

Chức năng:

- map attention weights `[49]`
- 48 sensor timesteps
- 1 weather token
- trả top-k `FeatureExplanation`
- detect trend bằng `_detect_trend`

---

## 11. Chức năng recommendation / irrigation decision

### FE xử lý

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

FE gọi recommendation sau prediction:

```ts
recommend({
  zone_id,
  prediction,
  telemetry,
  weather
})
```

Nếu chưa có prediction thật, FE có thể dùng:

```ts
buildFallbackPrediction(selectedZone)
```

FE hiển thị:

```ts
action
volume_mm
require_ack
reason
confidence_flag
degraded_mode
```

### API liên quan

```http
POST /v1/recommend
```

Schema:

File: `backend/core/schemas.py`

```py
RecommendRequest
IrrigationDecision
RecAction
```

### BE Gateway xử lý

File: `backend/api_gateway/main.py`

Route:

```py
recommend
```

Flow:

```text
POST /v1/recommend
-> api_gateway.main.recommend
-> request.app.state.decision_client.recommend(req)
```

Stub:

```text
StubDecisionClient.recommend
```

Live:

```text
LiveDecisionClient.recommend
-> decision_engine.main.evaluate_decision
```

### Decision Engine xử lý

File: `backend/decision_engine/main.py`

Route nội bộ:

```http
POST /internal/recommend
```

Core function:

```py
evaluate_decision(req: RecommendRequest) -> IrrigationDecision
```

Rule order:

1. rain override
2. uncertainty/degraded gate
3. critical stress
4. moderate stress
5. early watch
6. healthy range

Có wrapper khác:

File: `ai_system/decision_engine.py`

```py
make_decision
```

Nó wrap về logic chính trong `backend/decision_engine/main.py`.

---

## 12. Chức năng confirm irrigation command

### FE xử lý

File: `frontend/src/components/dashboard/ZoneOverlay.tsx`

Button confirm bị disable khi:

```ts
prediction ? prediction.uncertainty > 0.3 : true
```

Tức là:

- chưa có prediction -> không confirm
- uncertainty > 0.3 -> không confirm
- đang gửi command -> không confirm

Khi confirm:

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

```ts
createCommand({
  zone_id,
  action,
  volume_mm,
  source
})
```

### API liên quan

```http
POST /v1/commands
```

Schema:

File: `backend/core/schemas.py`

```py
IrrigationCommandRequest
IrrigationCommandResponse
CommandStatus
```

### BE xử lý

File: `backend/api_gateway/main.py`

Route:

```py
create_command
```

Gateway nhận command từ FE, validate auth role operator/admin, rồi trả command response.

---

## 13. Chức năng telemetry ingestion

### FE/API

FE client có function/API path cho telemetry auth:

```text
/v1/telemetry
```

API:

```http
POST /v1/telemetry
```

### BE Gateway xử lý

File: `backend/api_gateway/main.py`

Route:

```py
ingest_telemetry
```

Flow:

```text
POST /v1/telemetry
-> api_gateway.main.ingest_telemetry
-> request.app.state.ingestion_client.ingest(req)
```

### Ingestion Service xử lý

File: `backend/ingestion_service/main.py`

Routes:

| API | Mục đích |
|---|---|
| `GET /healthz` | health |
| `GET /readyz` | readiness |
| `POST /internal/telemetry` | nhận telemetry nội bộ |

Core functions:

```py
build_sample_id
ensure_zone_exists
persist_telemetry
```

Behavior:

- validate internal API key
- reject empty measurements
- require DB enabled
- insert vào table: `sensor_telemetry`

Schema:

File: `backend/core/schemas.py`

```py
TelemetryMeasurement
TelemetryIngestRequest
TelemetryIngestResponse
```

---

## 14. Chức năng zone status

### FE xử lý

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

Query:

```ts
getZoneStatus(selectedZoneId)
```

FE hiển thị:

- soil moisture
- air temp
- EC
- rain
- prediction summary
- recommendation summary
- imagery summary

Component liên quan:

```text
ZoneOverlay
DataFusionPanel
```

### API liên quan

```http
GET /v1/zones/{zone_id}/status
```

### BE xử lý

File: `backend/api_gateway/main.py`

Route:

```py
zone_status
```

Flow:

```text
zone_status
-> InMemoryZoneStatusCache
-> load_zone_feature
-> fetch_weather_for_zone
-> build_zone_status
-> demo prediction
-> LiveDecisionClient().recommend
-> build_alerts / build_zone_alert_records
```

Schema:

File: `backend/core/schemas.py`

```py
ZoneStatusResponse
AlertSummary
```

---

## 15. Chức năng alerts

### FE xử lý

File: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

Query:

```ts
getZoneAlerts(selectedZoneId)
```

Refetch interval:

```text
30s
```

### API liên quan

```http
GET /v1/zones/{zone_id}/alerts
```

### BE xử lý

File: `backend/api_gateway/main.py`

Route:

```py
zone_alerts
```

Alert schema:

File: `backend/core/schemas.py`

```py
AlertRecord
AlertFeedResponse
AlertSummary
```

Backend build alert từ trạng thái zone/prediction/decision/imagery.

---

## 16. Chức năng weather latest

### API hiện có

```http
GET /v1/zones/{zone_id}/weather/latest
```

### BE xử lý

File: `backend/api_gateway/main.py`

Route:

```py
zone_weather_latest
```

Flow liên quan:

```text
fetch_weather_for_zone
```

Config weather:

File: `backend/core/config.py`

```py
WEATHER_API_BASE_URL
```

FE survey không thấy route này được dùng trực tiếp trong dashboard chính, nhưng backend có API.

---

## 17. Chức năng health/readiness

### FE xử lý

Admin page gọi:

```ts
getHealth()
getReadiness()
```

File:

```text
frontend/src/features/admin/pages/AdminPage.tsx
```

### API Gateway

File: `backend/api_gateway/main.py`

```http
GET /v1/healthz
GET /v1/readyz
```

### AI Serving

File: `backend/ai_serving/main.py`

```http
GET /healthz
GET /public-healthz
GET /readyz
```

### Decision Engine

File: `backend/decision_engine/main.py`

```http
GET /healthz
GET /readyz
```

### Ingestion

File: `backend/ingestion_service/main.py`

```http
GET /healthz
GET /readyz
```

---

## 18. Chức năng Admin/Internal page

File: `frontend/src/features/admin/pages/AdminPage.tsx`

### Guard

Files:

- `frontend/src/lib/auth/guard.tsx`
- `frontend/src/lib/auth/token.ts`

Admin route chỉ bật khi:

```text
VITE_ENABLE_INTERNAL_ROUTES=true
```

Và có token:

```text
VITE_DEV_ACCESS_TOKEN
```

hoặc:

```text
localStorage['agmultida.accessToken']
```

### FE xử lý

Admin page có:

- health check
- readiness check
- list zones
- chọn zone
- run predict form
- run recommend form
- send irrigation command

Helper functions/components:

```ts
ZoneTable
NumberField
renderQueryState
renderMutationState
sanitizeReadiness
sanitizeZoneStatus
applyPredictToRecommend
applyRecommendationToCommand
```

### API liên quan

Admin dùng lại các API:

```http
GET /v1/healthz
GET /v1/readyz
GET /v1/zones
GET /v1/zones/{zone_id}/status
POST /v1/predict
POST /v1/recommend
POST /v1/commands
```

Admin có sanitize error:

```text
Service unavailable
```

Tránh lộ lỗi nội bộ.

---

## 19. Chức năng WebSocket updates

### API hiện có

File: `backend/api_gateway/main.py`

```http
WebSocket /ws/updates
```

FE có helper:

File: `frontend/src/lib/api/client.ts`

```ts
getWsUrl
```

Nhưng chưa thấy FE dashboard đang dùng WebSocket flow này.

---

## 20. ML training pipeline

Hiện đã có code train/export, dù model chưa hoàn hảo.

### Model

File:

```text
ml_pipeline/models/network.py
```

Class:

```py
MultimodalStressNet
```

Test cover:

- logits shape `[B, 1]`
- attention shape `[B, 49]`
- missing modality mask behavior

### Dataset

Files:

```text
ml_pipeline/data/dataset.py
ml_pipeline/data/sample.py
```

Classes:

```py
AgMultidaDataset
AlignedSample
```

Dataset item gồm:

```py
image
sensor_seq
weather_ctx
modality_mask
label
```

### Training

File:

```text
ml_pipeline/training/train.py
```

Functions:

```py
train_one_epoch
evaluate
main
```

Có hỗ trợ:

- manifest-backed training
- checkpoint writing

### Loss

File:

```text
ml_pipeline/training/losses.py
```

```py
ProxyRegressionLoss
```

### Metrics

File:

```text
ml_pipeline/training/metrics.py
```

```py
ContinuousMetrics
BinaryMetrics
```

### ONNX export

File:

```text
ml_pipeline/export/export_onnx.py
```

Entrypoint:

```py
main
```

---

## 21. Data pipeline / dataset preparation

Files chính:

```text
scripts/*.py
metadata/*.yaml
metadata/*.csv
metadata/*.geojson
dvc.yaml
```

Chức năng hiện có:

| Script | Mục đích |
|---|---|
| `scripts/run_data_collection.py` | Orchestrate thu thập dữ liệu |
| `scripts/download_sentinel2_gee.py` | Download Sentinel-2 qua GEE |
| `scripts/download_sentinel2_stac.py` | Download Sentinel-2 qua STAC |
| `scripts/download_chirps_direct.py` | Download CHIRPS |
| `scripts/download_chirps_gee.py` | Download CHIRPS qua GEE |
| `scripts/download_era5_land.py` | Download ERA5-Land |
| `scripts/download_open_meteo.py` | Download Open-Meteo |
| `scripts/download_smap.py` | Download SMAP |
| `scripts/process_era5_land.py` | Process ERA5-Land |
| `scripts/qa_sentinel2.py` | QA Sentinel-2 |
| `scripts/build_image_index.py` | Build image index |
| `scripts/build_environment_features.py` | Build env features |
| `scripts/generate_proxy_labels.py` | Generate proxy labels |
| `scripts/align_multimodal_samples.py` | Align image/sensor/weather samples |
| `scripts/create_spatiotemporal_splits.py` | Create train/val/test split |
| `scripts/package_dataset.py` | Package dataset |
| `scripts/build_dataset_card.py` | Build dataset card |
| `scripts/build_data_coverage_report.py` | Coverage report |

Metadata:

| File | Mục đích |
|---|---|
| `metadata/dataset_contract.yaml` | Contract dataset |
| `metadata/date_range.yaml` | Date range |
| `metadata/source_registry.yaml` | Source registry |
| `metadata/zone_registry.csv` | Zone registry |
| `metadata/zones.geojson` | Zone geometry |

---

## 22. Backend schemas/contracts

File: `backend/core/schemas.py`

Nhóm schema chính:

### Prediction

```py
PredictRequest
PredictResponse
FeatureImportance
ConfidenceFlag
```

### Recommendation

```py
RecommendRequest
IrrigationDecision
RecAction
```

### Telemetry

```py
TelemetryMeasurement
TelemetryIngestRequest
TelemetryIngestResponse
```

### Commands

```py
IrrigationCommandRequest
IrrigationCommandResponse
CommandStatus
```

### Zones / imagery / alerts

```py
ZoneStatusResponse
ZoneRegistryEntry
ZoneListResponse
ImagerySummary
ImageryScene
ImagerySceneCollection
AlertSummary
AlertRecord
AlertFeedResponse
```

### Health

```py
HealthResponse
```

---

## 23. Backend config/runtime

File: `backend/core/config.py`

Env quan trọng:

```py
GATEWAY_MODE
AI_SERVING_URL
INGESTION_SERVICE_URL
AI_SERVING_TIMEOUT_MS
INGESTION_SERVICE_TIMEOUT_MS
ONNX_MODEL_PATH
CALIBRATOR_PATH
MANIFEST_PATH
MODEL_VERSION
INTERNAL_API_KEY
INTERNAL_API_KEY_HEADER
DATABASE_URL
WEATHER_API_BASE_URL
REDIS_URL
```

Production guards:

- JWT secret required
- auth required
- HSTS required
- no wildcard/http CORS
- database required
- internal API key required

---

## 24. Security/auth/rate limit hiện có

Backend Gateway:

File: `backend/api_gateway/main.py`

Có role deps:

```py
require_role("viewer", "operator", "admin")
require_role("operator", "admin")
```

Dùng cho:

| Loại | Role |
|---|---|
| Read routes | `viewer`, `operator`, `admin` |
| Write routes | `operator`, `admin` |

Có limiter:

```py
zones limiter
admin limiter
```

Internal services dùng:

```py
INTERNAL_API_KEY
INTERNAL_API_KEY_HEADER
```

### Ghi chú phase hiện tại về lỗi 401

Hiện tại dự án thường gặp lỗi `401 Unauthorized` do chưa setup đầy đủ user/token, đặc biệt user `admin` và access token tương ứng.

Trong phase hiện tại, khi mục tiêu chính là demo, kiểm thử luồng chức năng, kiểm tra model, dashboard, imagery, prediction và recommendation, nên **tạm thời loại bỏ hoặc bypass cơ chế xác minh user/admin ở các API frontend đang dùng** để tránh lỗi xác thực làm gián đoạn kiểm thử.

Phạm vi nên tạm bypass:

| Nhóm API | API | Lý do |
|---|---|---|
| Zone/read APIs | `GET /v1/zones`, `GET /v1/zones/{zone_id}/status`, `GET /v1/zones/{zone_id}/alerts` | Dashboard cần load dữ liệu cơ bản |
| Imagery APIs | `GET /v1/zones/{zone_id}/imagery/latest`, `GET /v1/zones/{zone_id}/imagery/history`, `GET /v1/imagery/preview/{scene_id}` | Dashboard cần hiển thị RGB/NDVI |
| ML APIs | `POST /v1/predict`, `POST /v1/recommend` | Cần test luồng AI/model |
| Command demo API | `POST /v1/commands` | Cần test luồng xác nhận tưới trong demo |

Khuyến nghị triển khai trong phase này:

- Tắt requirement `Authorization: Bearer ...` cho local/dev/demo mode.
- Không yêu cầu user `admin` khi chạy dashboard/admin local.
- Giữ lại internal service key cho service-to-service nếu cần bảo vệ AI Serving/Ingestion nội bộ.
- Đánh dấu rõ đây là cấu hình tạm thời cho phase demo/dev, không dùng cho production.

Khi chuyển sang production hoặc phase hardening, cần bật lại:

- user/admin setup đầy đủ
- JWT/access token
- role-based access control
- rate limit
- audit log cho command tưới
- internal API key cho service nội bộ


---

## 25. Tests hiện có

### Backend API contract

Files:

```text
tests/backend/test_predict_contract.py
tests/backend/test_integration_wiring.py
```

Cover:

- `/v1/predict` schema
- invalid zone rejected
- extra fields rejected
- trace_id present
- `/v1/recommend` schema
- `/v1/healthz`
- no stacktrace leakage
- stub/live wiring
- timeout contract
- readiness
- internal API key guard

### Decision Engine

File:

```text
tests/ai_system/test_decision_engine.py
```

Cover:

- rain override
- uncertainty gate
- degraded mode hold
- critical branch
- moderate branch
- early watch branch
- healthy branch
- trace id invariant
- action volume invariant

### ML

Files:

```text
tests/ml/test_model_forward.py
tests/ml/test_dataset_contract.py
tests/ml/test_train_skeleton.py
tests/ml/test_checkpoint.py
tests/ml/test_loss_one_step.py
tests/ml/test_metrics.py
tests/ml/test_onnx_export_dryrun.py
```

Cover:

- model forward
- output shape
- attention masking
- missing modality
- dataset contract
- train/evaluate skeleton
- checkpoint
- loss one step
- metrics
- ONNX export dry run

### Data pipeline

Files:

```text
tests/data_pipeline/test_alignment_contract.py
tests/data_pipeline/test_collection_cli_contract.py
tests/data_pipeline/test_environment_features.py
tests/data_pipeline/test_no_leakage_split.py
tests/data_pipeline/test_proxy_labels.py
tests/data_pipeline/test_sentinel2_metadata.py
tests/data_pipeline/test_source_registry.py
tests/data_pipeline/test_zone_registry.py
```

Cover:

- alignment contract
- collection CLI contract
- environment features
- no leakage split
- proxy labels
- Sentinel metadata
- source registry
- zone registry

---

## 26. Danh sách API đầy đủ phát hiện được

### API Gateway public/admin

File: `backend/api_gateway/main.py`

| Method | Path | Function | Chức năng |
|---|---|---|---|
| GET | `/v1/healthz` | `healthz` | Health gateway |
| GET | `/v1/readyz` | `readyz` | Readiness gateway/deps |
| POST | `/v1/predict` | `predict` | Dự đoán stress ML |
| POST | `/v1/recommend` | `recommend` | Khuyến nghị tưới |
| POST | `/v1/telemetry` | `ingest_telemetry` | Nhận telemetry |
| POST | `/v1/commands` | `create_command` | Tạo lệnh tưới |
| GET | `/v1/zones` | `list_zones` | Danh sách zone |
| GET | `/v1/zones/{zone_id}/weather/latest` | `zone_weather_latest` | Weather mới nhất |
| GET | `/v1/zones/{zone_id}/status` | `zone_status` | Trạng thái zone tổng hợp |
| GET | `/v1/zones/{zone_id}/imagery/latest` | `zone_imagery_latest` | Ảnh mới nhất |
| GET | `/v1/zones/{zone_id}/imagery/history` | `zone_imagery_history` | Lịch sử ảnh |
| GET | `/v1/imagery/preview/{scene_id}` | `imagery_preview` | Preview PNG |
| GET | `/v1/zones/{zone_id}/alerts` | `zone_alerts` | Alert feed |
| WS | `/ws/updates` | `ws_updates` | WebSocket updates |

### AI Serving internal

File: `backend/ai_serving/main.py`

| Method | Path | Function | Chức năng |
|---|---|---|---|
| GET | `/healthz` | `healthz` | Health AI serving |
| GET | `/public-healthz` | `public_healthz` | Public health |
| GET | `/readyz` | `readyz` | Readiness model/manifest |
| POST | `/internal/predict` | `internal_predict` | Inference nội bộ |

### Decision Engine

File: `backend/decision_engine/main.py`

| Method | Path | Function | Chức năng |
|---|---|---|---|
| GET | `/healthz` | `healthz` | Health |
| GET | `/readyz` | `readyz` | Readiness |
| POST | `/internal/recommend` | `internal_recommend` | Recommend nội bộ |

### Ingestion Service

File: `backend/ingestion_service/main.py`

| Method | Path | Function | Chức năng |
|---|---|---|---|
| GET | `/healthz` | `healthz` | Health |
| GET | `/readyz` | `readyz` | Readiness |
| POST | `/internal/telemetry` | `ingest` | Ingest telemetry nội bộ |

---

## 27. Luồng nghiệp vụ chính end-to-end

### Luồng 1: User xem dashboard

```text
User mở /dashboard
-> FE load zones
-> FE load selected zone status
-> FE load imagery latest/history
-> FE load alerts
-> FE render map + panel + imagery
```

APIs:

```http
GET /v1/zones
GET /v1/zones/{zone_id}/status
GET /v1/zones/{zone_id}/imagery/latest
GET /v1/zones/{zone_id}/imagery/history
GET /v1/zones/{zone_id}/alerts
```

### Luồng 2: User chạy prediction

```text
User chọn zone
-> click/run prediction
-> FE POST /v1/predict
-> Gateway calls AI client
-> live mode calls AI Serving /internal/predict
-> AI Serving loads latest manifest sample
-> ONNX inference
-> post-process/calibration/explanation
-> Gateway returns PredictResponse
-> FE displays stress_prob/uncertainty/explanation
```

APIs:

```http
POST /v1/predict
POST /internal/predict
```

### Luồng 3: User chạy recommendation

```text
User có prediction
-> FE POST /v1/recommend
-> Gateway calls DecisionClient
-> Decision Engine evaluate_decision
-> returns action/volume/reason
-> FE displays irrigation decision
```

APIs:

```http
POST /v1/recommend
POST /internal/recommend
```

### Luồng 4: User confirm tưới

```text
FE kiểm tra uncertainty <= 0.3
-> FE POST /v1/commands
-> Gateway creates irrigation command
-> FE hiển thị result/status
```

API:

```http
POST /v1/commands
```

### Luồng 5: Sensor telemetry ingest

```text
Client/device POST /v1/telemetry
-> Gateway forwards to ingestion client
-> Ingestion service validates internal API key
-> builds sample_id
-> ensures zone exists
-> inserts sensor_telemetry
```

APIs:

```http
POST /v1/telemetry
POST /internal/telemetry
```

### Luồng 6: Imagery preview

```text
FE request latest/history
-> Gateway returns scene metadata
-> FE loads preview URL
-> Gateway imagery_preview builds/returns PNG
-> Map/Panel displays RGB or NDVI
```

APIs:

```http
GET /v1/zones/{zone_id}/imagery/latest
GET /v1/zones/{zone_id}/imagery/history
GET /v1/imagery/preview/{scene_id}
```

---

## 28. Nhận xét trạng thái hiện tại

- Model ML đã có đủ skeleton production path: dataset, train, ONNX export, ONNX serving, post-process, calibration, XAI.
- FE đã có dashboard hoàn chỉnh về mặt flow: zone -> imagery -> prediction -> recommendation -> command.
- Backend đã có API contracts khá đầy đủ.
- Nhiều flow có fallback demo/stub, nên app vẫn chạy khi ML/backend live chưa hoàn hảo.
- WebSocket đã có backend/helper nhưng FE chưa thấy dùng thật.
- Weather latest API có backend route nhưng FE dashboard chưa dùng trực tiếp.
- Admin route đã có nhưng bị guard bởi env/token.

---

## 29. Phân loại chức năng liên quan tới model

### Chức năng dùng model trực tiếp

Chỉ có chức năng prediction chạy model trực tiếp:

| Chức năng | API FE gọi | API nội bộ | BE xử lý | Ghi chú |
|---|---|---|---|---|
| Predict stress probability | `POST /v1/predict` | `POST /internal/predict` | `backend/api_gateway/main.py` -> `backend/ai_serving/main.py` -> ONNX inference | Đây là chức năng thật sự chạy model ML/ONNX |

Luồng xử lý:

```text
FE gọi POST /v1/predict
-> API Gateway nhận PredictRequest
-> LiveAIClient gọi AI Serving /internal/predict
-> AI Serving lấy sample từ manifest
-> ONNX model inference
-> PostProcessor xử lý probability/uncertainty/confidence
-> XAI explain_attention tạo explanation
-> trả PredictResponse về FE
```

Output model/AI chính:

```text
stress_prob
uncertainty
confidence_flag
degraded_mode
attention_weights
explanation
model_version
latency_ms
```

### Chức năng dùng kết quả model gián tiếp

Các chức năng dưới đây không chạy model, nhưng dùng output từ `predict` hoặc phụ thuộc vào luồng AI:

| Chức năng | API | Dùng gì từ model | Vai trò |
|---|---|---|---|
| Recommendation / irrigation decision | `POST /v1/recommend` | `stress_prob`, `uncertainty`, `confidence_flag`, `degraded_mode` | Rule engine sinh action/volume/reason |
| Confirm irrigation command | `POST /v1/commands` | Dùng recommendation đã sinh từ prediction | Gửi/xác nhận lệnh tưới |
| Zone status tổng hợp | `GET /v1/zones/{zone_id}/status` | Có thể chứa prediction/recommendation summary | Tổng hợp trạng thái vùng |
| Alerts | `GET /v1/zones/{zone_id}/alerts` | Có thể dựa trên stress/uncertainty/decision | Sinh cảnh báo vận hành |
| Dashboard display | `/dashboard` | Hiển thị toàn bộ prediction + recommendation | UI cho user xem và thao tác |

Kết luận:

- **Chạy model trực tiếp:** chỉ `predict`.
- **Dùng kết quả model gián tiếp:** `recommend`, `commands`, `zone status`, `alerts`, dashboard display.
- **Phục vụ model nhưng không phải chức năng inference:** imagery, telemetry, weather, data pipeline, training pipeline, ONNX export.

---

## 30. Tóm tắt ngắn

Tổng chức năng hiện có:

1. Landing page giới thiệu hệ thống.
2. Dashboard vận hành vùng canh tác.
3. Admin/internal operations page.
4. Zone selection và zone registry.
5. Map polygon bằng MapLibre.
6. Imagery RGB/NDVI latest/history/preview.
7. ML prediction stress probability.
8. Uncertainty/confidence/degraded mode handling.
9. XAI explanation từ attention weights.
10. Recommendation/decision engine cho tưới.
11. Confirm irrigation command.
12. Telemetry ingestion.
13. Zone status tổng hợp.
14. Alerts feed.
15. Weather latest API.
16. Health/readiness checks.
17. WebSocket updates endpoint.
18. ML dataset/training/evaluation/export ONNX.
19. Data collection/processing pipeline.
20. Security/auth/rate limit/internal API key guard.
