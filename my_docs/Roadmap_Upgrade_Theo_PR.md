# Roadmap Upgrade Theo PR - AgMultida

## 1. Mục tiêu roadmap

Roadmap này chia phiên đại tu AgMultida thành các PR nhỏ, có thứ tự phụ thuộc rõ.

Mục tiêu chính:

- Tận dụng model ML hiện tại đã xây dựng.
- Không train lại model trong phase này.
- Đưa output model hiện tại vào các chức năng vận hành:
  - prediction
  - recommendation
  - zone status
  - alerts
  - command safety gate
  - dashboard UI
  - realtime update
- Giảm lỗi `401 Unauthorized` ở môi trường dev/demo.
- Chuyển hệ thống từ demo/stub sang stable operational loop.
- Đại tu từng bước, tránh big-bang rewrite.

---

## 2. Nguyên tắc tận dụng model hiện tại

Model hiện tại đã có đủ pipeline cơ bản:

| Thành phần | File/Module | Vai trò |
|---|---|---|
| Model network | `ml_pipeline/models/network.py` | `MultimodalStressNet` |
| Dataset | `ml_pipeline/data/dataset.py` | Load image/sensor/weather/mask |
| Training skeleton | `ml_pipeline/training/train.py` | Train/evaluate/checkpoint |
| ONNX export | `ml_pipeline/export/export_onnx.py` | Export model phục vụ inference |
| AI Serving | `backend/ai_serving/main.py` | Load manifest + ONNX inference |
| ONNX wrapper | `backend/ai_serving/onnx_wrapper.py` | MC Dropout + timeout fallback |
| PostProcessor | `ai_system/post_processor.py` | calibration, EMA, uncertainty, confidence |
| XAI | `ai_system/xai_explainer.py` | explanation từ attention weights |

Trong đại tu này, **không thay model**. Thay vào đó:

1. Bọc model hiện tại bằng cache, safety policy, logging.
2. Dùng `PredictResponse` làm dữ liệu trung tâm cho các chức năng khác.
3. Dùng uncertainty/degraded mode để kiểm soát rủi ro.
4. Dùng rule engine hiện tại để biến prediction thành recommendation.
5. Dùng output prediction/recommendation để tạo alert/status/realtime.

Luồng trung tâm sau upgrade:

```text
Current ONNX model
-> POST /v1/predict
-> PredictResponse
-> Redis pred:{zone_id}:latest
-> Recommendation
-> Alert/Status/Command gate/WebSocket/Dashboard
```

---

## 3. Dependency graph tổng quát

```text
PR-01 Auth/Runtime guard
  -> PR-02 Zone registry/cache
  -> PR-03 Prediction cache + model reuse contract
      -> PR-04 Backend safety gate for commands
      -> PR-05 Recommendation from cached prediction
          -> PR-06 Zone status aggregate from model outputs
          -> PR-07 Alert lifecycle from model/recommendation outputs
              -> PR-08 Telegram worker
              -> PR-09 WebSocket realtime sync
  -> PR-10 Imagery proxy stability
  -> PR-11 Frontend dashboard store + model-driven UX
  -> PR-12 E2E hardening + docs
  -> PR-13 Backend feature refactor
```

Parallel có thể làm:

- PR-02 Zone registry và PR-10 Imagery proxy sau PR-01.
- PR-11 FE store có thể bắt đầu sau PR-01, nhưng model-driven UI cần PR-03/04/05 contract.
- PR-13 refactor nên làm cuối, sau behavior ổn.

---

# PR-01 - Runtime Guard, Dev Auth Bypass, Error Contract

## Mục tiêu

Giải quyết lỗi `401 Unauthorized` trong dev/demo do chưa setup user `admin`, nhưng không làm yếu production.

## BE scope

Files dự kiến:

```text
backend/core/config.py
backend/core/security.py
backend/api_gateway/main.py
backend/core/errors.py
```

Việc làm:

- Thêm/chuẩn hóa env:

```text
APP_ENV=development|demo|production
AUTH_REQUIRED=false
DEV_AUTH_BYPASS_ROLE=admin|operator|viewer
ALLOW_STUBS=true|false
WS_REQUIRE_AUTH=false
```

- `require_role()` cho phép dev claims khi:

```text
APP_ENV != production
AUTH_REQUIRED=false
```

- Production fail startup nếu:

```text
APP_ENV=production + AUTH_REQUIRED=false
APP_ENV=production + DEV_AUTH_BYPASS_ROLE set
APP_ENV=production + GATEWAY_MODE=stub
APP_ENV=production + ALLOW_STUBS=true
```

- Chuẩn hóa error response:

```json
{
  "error_code": "UNAUTHORIZED",
  "message": "Authentication required",
  "trace_id": "...",
  "timestamp": "..."
}
```

## FE scope

Files dự kiến:

```text
frontend/src/lib/auth/mode.ts
frontend/src/lib/auth/token.ts
frontend/src/lib/auth/guard.tsx
frontend/src/lib/api/client.ts
```

Việc làm:

- Thêm auth mode helper.
- Hiển thị dev bypass banner.
- 401 ở dev/demo hiển thị hướng dẫn, không chặn dashboard nếu bypass bật.
- 401 ở production không fallback demo âm thầm.

## Model liên quan

Không đụng model.

PR này mở đường để test `predict/recommend` không bị auth blocker.

## Tests

- local/dev không 401 khi `AUTH_REQUIRED=false`.
- production fail nếu bypass bật.
- unauthorized response đúng contract.

## Exit criteria

- Dashboard/admin local chạy được không cần user admin thật.
- Production guard có test.

---

# PR-02 - Zone Registry Service + Redis/Memory Cache

## Mục tiêu

Chuẩn hóa zone source để các chức năng model dùng cùng `zone_id` hợp lệ.

## BE scope

Files dự kiến:

```text
backend/features/zones/registry.py
backend/features/zones/schemas.py
backend/features/zones/router.py
backend/platform/cache.py
backend/api_gateway/main.py
metadata/zones.geojson
metadata/zone_registry.csv
```

Việc làm:

- Tạo `ZoneRegistryService`.
- Load `zones.geojson` + `zone_registry.csv` lúc startup.
- Validate geometry basic.
- Tính:
  - `center_latlon`
  - `bounds`
  - `coverage_score`
  - `crop_type`
  - `status`
- Cache:

```text
zones:registry TTL 24h
zones:{zone_id} TTL 24h
```

- `/v1/zones` dùng service mới, giữ response compatible.

## FE scope

Files dự kiến:

```text
frontend/src/features/dashboard/store/dashboardStore.ts
frontend/src/features/dashboard/pages/DashboardPage.tsx
frontend/src/components/dashboard/ZoneMap.tsx
```

Việc làm:

- Validate selected zone từ `/v1/zones`.
- Sync URL `?zone=ID`.
- Show coverage badge.

## Model liên quan

Model hiện tại cần `zone_id` để:

- tìm sample mới nhất trong manifest
- cache prediction theo zone
- link prediction -> recommendation -> alert

PR này đảm bảo mọi chức năng model downstream dùng zone registry chuẩn.

## Tests

- `/v1/zones` trả zone chuẩn.
- Invalid zone bị reject/fallback đúng.
- Redis down vẫn memory fallback.

## Exit criteria

- Dashboard chọn zone ổn.
- Predict request chỉ gửi zone hợp lệ.

---

# PR-03 - Prediction Cache + Reuse Current Model Output

## Mục tiêu

Tận dụng model hiện tại, biến `PredictResponse` thành dữ liệu trung tâm cho hệ thống.

## BE scope

Files dự kiến:

```text
backend/features/prediction/cache.py
backend/features/prediction/service.py
backend/features/prediction/policy.py
backend/api_gateway/clients/ai_client.py
backend/api_gateway/main.py
backend/ai_serving/main.py
backend/ai_serving/onnx_wrapper.py
ai_system/post_processor.py
```

Việc làm:

- Giữ flow model hiện tại:

```text
/v1/predict
-> LiveAIClient
-> /internal/predict
-> AI Serving
-> ONNX model
-> PostProcessor
-> XAI
```

- Sau khi predict thành công, lưu Redis:

```text
pred:{zone_id}:latest TTL 10m
pred:{zone_id}:{timestamp_bucket} TTL 30m
```

- Payload cache gồm:

```text
PredictResponse
created_at
source=live|demo|degraded
trace_id
model_version
```

- Không train lại model.
- Không đổi kiến trúc model.
- Bổ sung logging:

```json
{
  "event": "prediction_completed",
  "zone_id": "A01",
  "stress_prob": 0.72,
  "uncertainty": 0.18,
  "degraded_mode": false,
  "latency_ms": 421,
  "trace_id": "..."
}
```

## API contract

Giữ:

```http
POST /v1/predict
```

Output tiếp tục gồm:

```text
stress_prob
uncertainty
confidence_flag
degraded_mode
attention_weights
explanation
model_version
latency_ms
trace_id
```

Có thể thêm optional:

```json
{
  "prediction_id": "pred_A01_20260509T120000Z"
}
```

## FE scope

Files dự kiến:

```text
frontend/src/features/dashboard/hooks/usePredictionFlow.ts
frontend/src/features/dashboard/pages/DashboardPage.tsx
frontend/src/components/dashboard/ZoneOverlay.tsx
frontend/src/components/dashboard/DegradationBanner.tsx
```

Việc làm:

- `Run Prediction` gọi API như hiện tại.
- Hiển thị rõ:
  - stress gauge
  - uncertainty badge
  - confidence
  - degraded banner
  - XAI top features
- Nếu trace demo: show demo warning.

## Model liên quan

Đây là PR trung tâm tận dụng model hiện tại.

Không cải thiện accuracy bằng training. Cải thiện operational safety bằng:

- uncertainty gating
- degraded mode
- timeout fallback
- cache latest prediction
- audit trace

## Tests

- `/v1/predict` live/stub contract pass.
- Prediction success writes Redis cache.
- AI timeout returns degraded mode.
- Missing modality affects uncertainty/degraded flag.
- Log contains trace/model fields.

## Exit criteria

- Có thể gọi predict 1 lần, rồi downstream đọc `pred:{zone_id}:latest`.
- Model output hiện tại được dùng lại trong hệ thống, không chỉ hiển thị FE.

---

# PR-04 - Backend Command Safety Gate From Prediction

## Mục tiêu

Không để FE là lớp an toàn duy nhất. Backend phải chặn command nếu prediction từ model không đủ tin cậy.

## BE scope

Files dự kiến:

```text
backend/features/commands/service.py
backend/features/prediction/policy.py
backend/features/prediction/cache.py
backend/api_gateway/main.py
backend/core/schemas.py
```

Việc làm:

- Khi `POST /v1/commands`, backend load latest prediction:

```text
pred:{zone_id}:latest
```

- Reject nếu:

```text
prediction missing
uncertainty > 0.30
degraded_mode=true and no manual ack/local override
trace_id starts with demo- in production
prediction expired
```

- Error code:

```text
COMMAND_BLOCKED_HIGH_UNCERTAINTY
COMMAND_BLOCKED_DEGRADED_PREDICTION
COMMAND_BLOCKED_NO_RECENT_PREDICTION
```

## API contract

```http
POST /v1/commands
```

Blocked response:

```http
409 Conflict
```

```json
{
  "error_code": "COMMAND_BLOCKED_HIGH_UNCERTAINTY",
  "message": "Latest prediction uncertainty is too high for automatic irrigation",
  "trace_id": "...",
  "timestamp": "..."
}
```

## FE scope

- Confirm button disabled lý do rõ.
- Nếu BE reject, show same reason.
- Không cho confirm local demo result.

## Model liên quan

Dùng trực tiếp `uncertainty`, `degraded_mode`, `trace_id`, `created_at` từ model output đã cache.

Model hiện tại chưa hoàn hảo, nên PR này biến uncertainty thành lớp an toàn vận hành.

## Tests

- Command blocked nếu uncertainty > 0.3.
- Command blocked nếu missing prediction.
- Command blocked nếu degraded without ack.
- Command allowed nếu prediction fresh + uncertainty thấp.

## Exit criteria

- Không có command nguy hiểm khi model không chắc chắn.

---

# PR-05 - Recommendation From Cached Prediction

## Mục tiêu

Recommendation dùng output model hiện tại từ cache, giảm FE phải gửi lại full prediction.

## BE scope

Files dự kiến:

```text
backend/features/recommendation/service.py
backend/features/recommendation/router.py
backend/features/prediction/cache.py
backend/decision_engine/main.py
backend/api_gateway/clients/decision_client.py
```

Việc làm:

- Giữ API cũ:

```http
POST /v1/recommend
```

- Thêm API optional:

```http
POST /v1/recommend/from-cache
```

- Flow:

```text
zone_id
-> load pred:{zone_id}:latest
-> load telemetry/weather latest/mock
-> evaluate_decision()
-> store decision:{zone_id}:latest
-> maybe emit alert event
```

- Không gọi model trong recommend.

## API contract

Input:

```json
{
  "zone_id": "A01",
  "prediction_id": null
}
```

Output:

```json
{
  "zone_id": "A01",
  "action": "light_irrigation",
  "volume_mm": 5.0,
  "require_ack": true,
  "reason": "medium_stress_low_moisture",
  "confidence_flag": "medium",
  "degraded_mode": false,
  "trace_id": "..."
}
```

Cache miss:

```http
409 Conflict
```

```json
{
  "error_code": "PREDICTION_CACHE_MISS",
  "message": "Run prediction before requesting recommendation",
  "trace_id": "..."
}
```

## FE scope

- Sau predict success, gọi recommend.
- Nếu API from-cache có, gọi from-cache.
- Nếu chưa có, fallback API cũ với full prediction.
- Show reason/require_ack.

## Model liên quan

Dùng kết quả model gián tiếp:

```text
stress_prob
uncertainty
confidence_flag
degraded_mode
```

Rule engine tận dụng model hiện tại bằng policy:

```text
rain override
uncertainty gate
stress + moisture logic
```

## Tests

- Recommend from-cache hit.
- Cache miss 409.
- Rain > 15mm/3h -> no_irrigation.
- Uncertainty > 0.3 -> hold.
- Decision latest saved.

## Exit criteria

- Recommendation phụ thuộc output model hiện tại nhưng không chạy model.

---

# PR-06 - Zone Status Aggregate From Model Outputs

## Mục tiêu

Zone status hiển thị trạng thái tổng hợp thật hơn, lấy latest prediction/recommendation từ cache thay vì demo inline.

## BE scope

Files dự kiến:

```text
backend/features/zones/status_service.py
backend/features/prediction/cache.py
backend/features/recommendation/service.py
backend/features/imagery/service.py
backend/features/alerts/service.py
backend/api_gateway/main.py
```

Việc làm:

- Tạo `ZoneStatusService`.
- Aggregate:

```text
zone registry
latest telemetry
latest weather
latest imagery
pred:{zone_id}:latest
decision:{zone_id}:latest
alerts summary
```

- Cache aggregate:

```text
zone_status:{zone_id} TTL 30-120s
```

- Invalidate khi:
  - prediction mới
  - recommendation mới
  - imagery mới
  - alert mới
  - telemetry mới

## API contract

Giữ:

```http
GET /v1/zones/{zone_id}/status
```

Bổ sung fields nếu chưa có:

```json
{
  "zone_id": "A01",
  "prediction": {
    "stress_prob": 0.72,
    "uncertainty": 0.18,
    "confidence_flag": "medium",
    "degraded_mode": false,
    "model_version": "onnx-v1"
  },
  "recommendation": {
    "action": "light_irrigation",
    "volume_mm": 5.0,
    "reason": "medium_stress_low_moisture"
  },
  "imagery": {
    "stale": false,
    "cloud_cover": 18.5
  },
  "alerts": {
    "open_count": 1,
    "highest_severity": "moderate"
  }
}
```

## FE scope

- `DataFusionPanel` và `ZoneOverlay` dùng status aggregate.
- Nếu no prediction: prompt user run prediction.
- Nếu prediction stale: show stale model output badge.

## Model liên quan

Status trở thành nơi tái sử dụng output model hiện tại cho toàn dashboard.

Không cần chạy predict lại mỗi lần render status.

## Tests

- Status reads prediction cache.
- Status reads decision cache.
- Missing prediction trả state rõ, không fake silently.
- Status invalidated after predict/recommend.

## Exit criteria

- Dashboard status phản ánh latest model output.

---

# PR-07 - Alert Lifecycle From Prediction/Recommendation

## Mục tiêu

Dùng kết quả model hiện tại để tạo alert vận hành.

## BE scope

Files dự kiến:

```text
backend/features/alerts/service.py
backend/features/alerts/stream.py
backend/features/alerts/lifecycle.py
backend/features/recommendation/service.py
backend/features/prediction/policy.py
backend/api_gateway/main.py
```

Việc làm:

- Khi recommendation sinh:

```text
action != no_irrigation
uncertainty medium/high
degraded_mode true
stress_prob critical
imagery stale
```

thì tạo alert.

- Redis structures:

```text
alerts:events
alert:{alert_id}
alerts:zone:{zone_id}:open
```

- Alert lifecycle:

```text
open -> notified -> acknowledged -> resolved
```

- Ack API:

```http
POST /v1/alerts/{id}/ack
```

## API contract

```http
GET /v1/zones/{zone_id}/alerts
POST /v1/alerts/{id}/ack
```

Alert item:

```json
{
  "id": "alert_123",
  "zone_id": "A01",
  "type": "irrigation_required",
  "severity": "moderate",
  "status": "open",
  "reason": "stress high and moisture low",
  "telegram_sent": false,
  "created_at": "..."
}
```

## FE scope

- Add `AlertFeed`.
- Show severity colors.
- Ack button.
- Click alert pan map to zone.

## Model liên quan

Alert rules dùng:

```text
stress_prob
uncertainty
confidence_flag
degraded_mode
recommendation action
```

Model chưa hoàn hảo nên alert phải phân loại:

- high uncertainty: cảnh báo review, không hành động tự động
- low uncertainty + high stress: alert tưới đáng tin hơn

## Tests

- High stress creates alert.
- High uncertainty creates hold/review alert.
- Ack updates status.
- Duplicate alert dedupe.

## Exit criteria

- Model output tạo được alert có lifecycle.

---

# PR-08 - Telegram Worker For Alerts

## Mục tiêu

Đẩy alert quan trọng qua Telegram, không block request chính.

## BE scope

Files dự kiến:

```text
backend/features/alerts/telegram_worker.py
backend/features/alerts/stream.py
backend/core/config.py
```

Việc làm:

- Worker đọc Redis Stream `alerts:events`.
- Gửi Telegram khi:

```text
severity in [moderate, critical]
status=open
telegram_sent=false
```

- Lưu:

```text
telegram_msg_id
telegram_sent=true
status=notified
```

- Retry backoff.
- DLQ nếu fail quá ngưỡng.

## Config

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ALERT_TELEGRAM_ENABLED=true|false
```

Production guard:

- Nếu Telegram enabled mà thiếu token/chat -> readiness degraded hoặc fail tùy env.

## Model liên quan

Telegram không dùng model trực tiếp.

Nó dùng alert đã sinh từ prediction/recommendation.

## Tests

- Worker sends once.
- Duplicate event no duplicate Telegram.
- Telegram failure retries.
- Disabled config skips send.

## Exit criteria

- Alert critical được push ngoài UI.

---

# PR-09 - WebSocket Realtime Sync

## Mục tiêu

Realtime hóa dashboard bằng event sinh từ prediction/recommendation/alert/status.

## BE scope

Files dự kiến:

```text
backend/features/websocket/manager.py
backend/features/websocket/router.py
backend/features/websocket/redis_subscriber.py
backend/features/websocket/schemas.py
```

Việc làm:

- WebSocket manager.
- Redis Pub/Sub subscriber.
- PING/PONG 30s.
- Publish event khi:
  - prediction completed
  - recommendation created
  - alert opened/acked
  - status changed
  - imagery updated

Channels:

```text
ws:broadcast
ws:zone:{zone_id}
system:alerts
system:health
```

## FE scope

Files dự kiến:

```text
frontend/src/lib/realtime/useWebSocket.ts
frontend/src/lib/realtime/types.ts
frontend/src/features/dashboard/store/dashboardStore.ts
```

Việc làm:

- Connect on dashboard mount.
- Subscribe selected zone.
- Reconnect exponential.
- Invalidate React Query keys by event.
- Show live/reconnecting/offline pill.

## Model liên quan

Prediction hoàn tất -> publish event:

```json
{
  "event": "prediction_completed",
  "payload": {
    "zone_id": "A01",
    "stress_prob": 0.72,
    "uncertainty": 0.18,
    "confidence_flag": "medium"
  }
}
```

FE dùng event để refresh status/UI, không cần user reload.

## Tests

- WS connect/reconnect.
- Event invalidates status/alerts queries.
- Prediction event updates model UI state.
- WS down keeps polling fallback.

## Exit criteria

- Model/recommend/alert result cập nhật realtime trên dashboard.

---

# PR-10 - Imagery Proxy Stability With Redis/MinIO/Circuit Breaker

## Mục tiêu

Ổn định imagery để hỗ trợ model/dashboard mà không làm UI blank.

## BE scope

Files dự kiến:

```text
backend/features/imagery/service.py
backend/features/imagery/persistence.py
backend/features/imagery/circuit_breaker.py
backend/core/imagery_proxy.py
backend/core/config.py
```

Việc làm:

- Redis metadata cache.
- MinIO preview storage.
- Circuit breaker provider.
- Placeholder fallback.
- Preserve SSRF URL guard.

## FE scope

Files dự kiến:

```text
frontend/src/components/dashboard/ZoneImageryPanel.tsx
frontend/src/components/dashboard/ImageryTimeline.tsx
frontend/src/components/dashboard/ZoneMap.tsx
```

Việc làm:

- Timeline lazy load.
- Session/query cache preview URL.
- Fresh/cloudy/stale badges.
- Placeholder state.

## Model liên quan

Imagery là input/phục vụ model, không phải inference trực tiếp.

Trong phase này:

- Không rebuild training dataset.
- Dùng imagery metadata/status để giải thích dashboard và degraded signal.
- Nếu imagery stale/missing, prediction/recommendation có thể tăng degraded/caution trong UI.

## Tests

- Provider 429/5xx opens breaker.
- MinIO hit avoids render.
- Placeholder returns degraded.
- FE stale badge visible.

## Exit criteria

- Imagery lỗi không làm fail predict/recommend dashboard flow.

---

# PR-11 - Frontend Dashboard Store + Model-Driven UX

## Mục tiêu

FE phản ánh rõ model hiện tại đang quyết định gì, độ tin cậy ra sao, và vì sao không cho hành động.

## FE scope

Files dự kiến:

```text
frontend/src/features/dashboard/store/dashboardStore.ts
frontend/src/features/dashboard/hooks/usePredictionFlow.ts
frontend/src/features/dashboard/hooks/useDashboardQueries.ts
frontend/src/features/dashboard/hooks/useDegradationSignals.ts
frontend/src/components/dashboard/DegradationBanner.tsx
frontend/src/components/dashboard/AlertFeed.tsx
frontend/src/components/dashboard/ZoneOverlay.tsx
frontend/src/features/dashboard/pages/DashboardPage.tsx
```

Việc làm:

- Zustand store:
  - selected zone
  - imagery mode
  - selected scene
  - ws status
  - ack local state
- Prediction flow hook:
  - predict
  - recommend
  - confirm command
- Degradation signals:
  - demo trace
  - degraded mode
  - stale imagery
  - WS offline
  - auth bypass
  - backend unavailable
- Confirm disabled reasons:
  - no prediction
  - high uncertainty
  - degraded mode
  - demo result
  - no recommendation
  - ack required

## Model liên quan

UI phải hiển thị model output như first-class data:

```text
stress_prob gauge
uncertainty badge
confidence flag
model_version
latency
XAI top features
degraded mode banner
```

Không để model chỉ là số phụ trong panel.

## Tests

- High uncertainty disables confirm.
- Degraded mode banner visible.
- Demo trace banner visible.
- XAI features render.
- Recommendation reason tooltip render.

## Exit criteria

- User nhìn dashboard biết model đang dự đoán gì, tin cậy bao nhiêu, và vì sao hệ thống cho/không cho tưới.

---

# PR-12 - E2E, Fallback Validation, Load/Failure Tests

## Mục tiêu

Chứng minh hệ thống đại tu chạy được golden path và failure path.

## Scope

Backend tests:

```text
tests/backend/test_predict_contract.py
tests/backend/test_integration_wiring.py
new tests/backend/test_prediction_cache.py
new tests/backend/test_command_safety_gate.py
new tests/backend/test_recommend_from_cache.py
new tests/backend/test_alert_lifecycle.py
new tests/backend/test_runtime_guard.py
```

Frontend tests:

```text
frontend/src/features/dashboard/dashboard.test.tsx
frontend/src/components/dashboard/DegradationBanner.test.tsx
frontend/src/components/dashboard/AlertFeed.test.tsx
frontend/src/lib/realtime/useWebSocket.test.tsx
frontend/tests/e2e/upgrade_operational_loop.spec.ts
```

Golden path:

```text
Open dashboard
-> load zones
-> select zone
-> latest imagery loads
-> run prediction with current model
-> result cached
-> get recommendation from model output
-> command allowed/rejected by safety policy
-> alert created if needed
-> websocket updates UI
```

Failure path:

```text
401 dev bypass
503 backend fallback
imagery provider timeout
model timeout degraded mode
uncertainty > 0.3 command blocked
websocket disconnect fallback polling
```

## Model liên quan

Tests phải dùng model path hiện tại ở mức contract/integration.

Không cần assert accuracy. Assert operational behavior:

- response shape
- uncertainty gate
- cache write
- degraded fallback
- downstream consumption

## Exit criteria

- Golden path pass.
- Failure path pass.
- Không blank screen.
- Không command unsafe.

---

# PR-13 - Backend Feature Refactor After Behavior Stable

## Mục tiêu

Sau khi behavior ổn, refactor backend theo cấu trúc `Tai_cau_truc.md`.

## Scope

Target:

```text
backend/
├── apps/
├── features/
└── platform/
```

Thứ tự:

1. Tách health router.
2. Tách zones router/service.
3. Tách prediction router/service/cache.
4. Tách recommendation router/service.
5. Tách commands router/service.
6. Tách imagery router/service.
7. Tách alerts router/service.
8. Tách websocket router/manager.
9. Tách platform config/errors/security/cache/storage.
10. Tách schemas theo feature.

## Model liên quan

Giữ model path không đổi trước:

```text
backend/ai_serving/main.py
backend/ai_serving/onnx_wrapper.py
ai_system/post_processor.py
ai_system/xai_explainer.py
```

Chỉ refactor gateway/orchestration quanh model, không refactor model pipeline cùng lúc.

## Tests

- Route contract cũ pass.
- Import compatibility pass.
- Docker entrypoint mới pass.
- No new `sys.path.insert`.

## Exit criteria

- `api_gateway/main.py` chỉ còn wiring/middleware/include router.
- Feature code nằm đúng domain.
- Model-serving flow vẫn chạy y nguyên.

---

## 4. PR ưu tiên nếu thời gian ít

Nếu chỉ có thời gian làm nhóm nhỏ trước, chọn:

1. **PR-01**: Auth bypass + runtime guard.
2. **PR-03**: Prediction cache tận dụng model hiện tại.
3. **PR-04**: Backend command safety gate.
4. **PR-05**: Recommendation từ cached prediction.
5. **PR-11**: FE model-driven UX.

5 PR này đủ để chứng minh:

```text
Model hiện tại -> prediction -> recommendation -> safe command -> dashboard rõ ràng
```

---

## 5. Tiêu chí hoàn thành toàn bộ roadmap

Hệ thống được xem là qua đại tu phase này khi:

- Local/dev không bị chặn bởi 401 admin/token.
- Production không cho auth bypass/stub.
- `/v1/predict` dùng model hiện tại và cache latest prediction.
- `/v1/recommend` hoặc `/v1/recommend/from-cache` dùng cached model output.
- `/v1/commands` enforce uncertainty/degraded gate ở backend.
- `/v1/zones/{id}/status` phản ánh prediction/recommendation latest.
- Alert được sinh từ model/recommendation output.
- Telegram worker xử lý alert quan trọng.
- WebSocket cập nhật dashboard realtime.
- Imagery lỗi vẫn có fallback/degraded UI.
- FE hiển thị rõ stress, uncertainty, confidence, degraded, reason.
- E2E golden path và failure path pass.

---

## 6. Kết luận

Roadmap này không xem model hiện tại là phần tách rời hay chưa dùng được.

Ngược lại, model hiện tại là lõi của đại tu:

```text
PredictResponse từ model hiện tại
-> cache
-> recommendation
-> command safety
-> status aggregate
-> alerts
-> realtime dashboard
```

Do model chưa hoàn hảo, hệ thống không cố tự động hóa mù quáng. Thay vào đó, dùng:

- uncertainty gating
- degraded mode
- EMA smoothing
- rain override
- manual ack
- audit log
- backend command reject

để biến model hiện tại thành một thành phần vận hành an toàn trong phase này.
