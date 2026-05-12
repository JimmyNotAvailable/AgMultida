# Kế Hoạch Upgrade Đại Tu Hệ Thống AgMultida

## 1. Mục tiêu phiên upgrade

Phiên upgrade này chuyển hệ thống từ trạng thái **demo/stub + nhiều fallback rời rạc** sang trạng thái **stable operational loop**.

Mục tiêu chính:

- Giữ lại các chức năng đã có: zone, map, imagery, predict, recommend, command, alerts, websocket, ML pipeline.
- Chuẩn hóa BE/API/FE theo 7 chức năng cốt lõi.
- Giảm lỗi `401 Unauthorized` trong phase dev/demo do chưa setup user `admin`.
- Không train lại model trong phase này.
- Tăng độ an toàn bằng uncertainty gating, degraded mode, rain override, audit log.
- Tách dần `api_gateway/main.py` khỏi vai trò god file.
- Ưu tiên Redis/memory/MinIO thay vì migration DB lớn.
- Đảm bảo UI không blank screen khi backend, imagery provider, websocket, model inference lỗi.

---

## 2. Đánh giá hệ thống hiện tại

### 2.1 Kiến trúc hiện tại

Backend hiện chia theo service kỹ thuật:

```text
backend/
├── api_gateway/
├── ai_serving/
├── decision_engine/
├── ingestion_service/
└── core/
```

Frontend hiện có:

```text
frontend/src/
├── app/
├── components/
├── features/
├── lib/
└── tests/
```

Các chức năng chính đã có:

| Chức năng | Trạng thái hiện tại |
|---|---|
| Zone registry | Có, dựa vào file/local metadata |
| Map polygon | Có, dùng MapLibre |
| Imagery latest/history/preview | Có, qua API gateway + imagery proxy |
| Predict ML | Có, chạy ONNX qua AI Serving khi live mode |
| Recommend | Có, rule engine trong Decision Engine |
| Command confirm | Có, FE gate theo uncertainty; BE chưa enforce đủ |
| Alerts | Có feed cơ bản; chưa có Telegram/worker lifecycle đầy đủ |
| WebSocket | Có endpoint `/ws/updates`; FE chưa subscribe thật |
| Telemetry ingest | Có ingestion service, còn phụ thuộc DB |
| Health/readiness | Có, nhưng cần mở rộng dependency readiness |
| Auth/role | Có, nhưng dev/demo hay lỗi `401` do chưa setup admin/token |
| Stub/demo fallback | Có nhiều, giúp demo nhưng dễ che lỗi integration |

---

## 3. Vấn đề lớn cần xử lý

### 3.1 Backend gateway quá nhiều trách nhiệm

File `backend/api_gateway/main.py` hiện ôm nhiều logic:

- middleware
- auth dependency
- rate limit
- zone registry
- weather
- imagery
- alerts
- websocket
- command endpoint
- status aggregation

Rủi ro:

- khó test
- khó mở rộng
- dễ gãy khi thêm Redis/MinIO/WebSocket worker
- khó tách dev/demo/prod behavior

### 3.2 `core/schemas.py` quá lớn

File `backend/core/schemas.py` gom nhiều domain:

- prediction
- recommendation
- telemetry
- commands
- zones
- imagery
- alerts
- health

Rủi ro:

- blast radius lớn khi đổi contract
- feature khó tự quản schema riêng
- test import phụ thuộc mạnh vào `core.schemas`

### 3.3 Gating an toàn mới nằm nhiều ở FE

FE hiện block confirm khi:

```ts
prediction.uncertainty > 0.3
```

Nhưng backend command endpoint cần enforce lại.

Không được để FE là lớp an toàn duy nhất.

### 3.4 Auth gây chặn dev/demo

Hiện hay gặp:

```text
401 Unauthorized
```

Nguyên nhân:

- chưa setup user `admin`
- thiếu access token
- FE attach token theo path nhưng môi trường local/demo chưa có token
- admin route bị guard

Phase hiện tại cần bypass rõ ràng cho dev/demo, nhưng production phải fail fast nếu bypass bật.

### 3.5 Realtime chưa thành loop vận hành

Có WebSocket route nhưng chưa thành pipeline:

```text
Prediction/Recommendation/Alert
-> Redis Pub/Sub hoặc Stream
-> Gateway WebSocket manager
-> FE Zustand/React Query update
```

### 3.6 Alert chưa có lifecycle đầy đủ

Hiện alert feed chủ yếu là read-only.

Cần lifecycle:

```text
open -> notified -> acknowledged -> resolved
```

Và cần Telegram push cho alert quan trọng.

---

## 4. Nguyên tắc upgrade

### 4.1 Không big-bang rewrite

Không viết lại toàn bộ một lần.

Dùng kiểu strangler pattern:

1. Giữ API cũ đang được FE dùng.
2. Thêm service/cache/repository layer mới bên dưới.
3. Chuyển từng route sang service mới.
4. Khi ổn mới tách router/schema.

### 4.2 API cũ phải giữ tương thích

Các API FE đang gọi phải tiếp tục hoạt động:

```http
GET /v1/zones
GET /v1/zones/{zone_id}/status
GET /v1/zones/{zone_id}/alerts
GET /v1/zones/{zone_id}/imagery/latest
GET /v1/zones/{zone_id}/imagery/history
GET /v1/imagery/preview/{scene_id}
POST /v1/predict
POST /v1/recommend
POST /v1/commands
GET /v1/healthz
GET /v1/readyz
WS /ws/updates
```

### 4.3 Redis là trục cache/realtime

Redis dùng cho:

- zone registry cache
- prediction latest cache
- decision latest cache
- zone status aggregate cache
- imagery metadata cache
- alert stream/hash
- websocket pub/sub
- circuit breaker state

### 4.4 MinIO dùng cho object/preview

MinIO dùng cho:

- cached imagery preview PNG
- raw/processed imagery object
- signed URL TTL ngắn

Không nhét binary ảnh vào SQL.

### 4.5 DB phase này tối giản

Không migration lớn.

Ưu tiên:

- memory cache cho local
- Redis cho cache nóng
- MinIO cho object
- stdout JSON log cho audit

DB/Timescale/PostGIS để phase sau.

---

## 5. Thiết kế upgrade theo 7 chức năng cốt lõi

---

# 5.1 Quản lý Zone & Bản đồ thực địa

## Hiện tại

FE:

- `ZoneMap` render polygon bằng MapLibre.
- Zone selection sync với URL `?zone=ID`.
- Zone data chủ yếu từ local/dashboard data và API `/v1/zones`.

BE:

- `GET /v1/zones` có trong gateway.
- Zone registry đọc từ metadata/local files.
- Geometry và coverage chưa được chuẩn hóa thành service riêng.

## Mục tiêu upgrade

Tạo `ZoneRegistryService` làm nguồn chuẩn cho zone.

## Thiết kế BE

Service đề xuất:

```text
backend/features/zones/
├── router.py
├── schemas.py
├── registry.py
└── status_service.py
```

Nguồn dữ liệu phase này:

```text
metadata/zones.geojson
metadata/zone_registry.csv
```

Luồng boot:

```text
App startup
-> load zones.geojson
-> validate geometry
-> merge zone_registry.csv metadata
-> compute center_latlon/bounds
-> compute coverage_score mock/basic
-> write memory cache
-> optional write Redis zones:registry TTL 24h
```

Validation geometry:

- Phase nhanh: validate basic GeoJSON coordinates/bounds.
- Nếu dependency có sẵn: dùng `shapely.is_valid`.
- Không thêm PostGIS phase này.

Coverage score:

- Phase hiện tại: tính đơn giản từ mật độ sensor/sample trong bounding box nếu có metadata.
- Nếu chưa có sensor points thật: trả score mock/derived từ registry và flag `coverage_source="estimated"`.

## Hợp đồng API

Giữ API:

```http
GET /v1/zones
```

Response target:

```json
{
  "zones": [
    {
      "zone_id": "A01",
      "name": "Zone A01",
      "center_latlon": [10.123, 106.456],
      "bounds": [106.1, 10.1, 106.2, 10.2],
      "coverage_score": 82,
      "crop_type": "rice",
      "status": "healthy"
    }
  ],
  "trace_id": "..."
}
```

## Chiến lược DB/cache

Không dùng DB phase này.

Cache:

| Key | TTL | Nội dung |
|---|---:|---|
| `zones:registry` | 24h | full normalized zone list |
| `zones:{zone_id}` | 24h | one zone detail |
| memory L1 | process lifetime | fallback khi Redis down |

## FE gọi

Dashboard mount:

```text
GET /v1/zones
-> setZones() vào Zustand dashboard store
-> validate ?zone=ID
-> setSelectedZoneId()
```

## UI/UX

- Polygon mặc định xám nhạt.
- Hover tooltip:
  - tên zone
  - crop type
  - coverage score
  - status
- Click zone:
  - highlight viền xanh đậm
  - sync URL
  - fetch status/imagery/predict readiness
- Badge coverage:
  - `>= 70%`: xanh
  - `< 70%`: vàng cảnh báo
  - missing coverage: xám + tooltip "estimated"

## Nghiệm thu

- `/v1/zones` trả list chuẩn từ GeoJSON/CSV.
- Redis down vẫn trả bằng memory cache.
- FE chọn zone từ map/list đều sync URL.
- Zone không hợp lệ trong URL tự fallback zone mặc định.

---

# 5.2 Imagery Proxy & Timeline

## Hiện tại

FE:

- `ZoneImageryPanel` hiển thị RGB/NDVI.
- `ImageryTimeline` hiển thị history.
- `ZoneMap` overlay imagery.

BE:

- `backend/core/imagery_proxy.py` build preview PNG.
- Có latest/history/preview API.
- Có fallback placeholder/demo.
- Chưa có MinIO/Redis metadata/circuit breaker rõ.

## Mục tiêu upgrade

FE không gọi 3rd party trực tiếp.

Gateway/proxy chịu trách nhiệm:

```text
Request imagery
-> metadata cache Redis
-> object cache MinIO
-> provider fetch/render nếu cần
-> signed URL hoặc preview URL
-> fallback local demo/degraded nếu lỗi
```

## Thiết kế BE

Feature đề xuất:

```text
backend/features/imagery/
├── router.py
├── schemas.py
├── service.py
├── persistence.py
├── preview.py
└── circuit_breaker.py
```

Luồng latest:

```text
GET /v1/zones/{id}/imagery/latest
-> ImageryService.get_latest(zone_id)
-> Redis metadata hit? return
-> provider allowed? fetch metadata
-> cache metadata Redis TTL 15m
-> return scene metadata
```

Luồng preview:

```text
GET /v1/imagery/preview/{scene_id}
-> check MinIO object preview exists
-> if exists: return signed URL/redirect/proxy bytes
-> if not: check breaker
-> if closed/half-open: render PNG from source
-> store PNG in MinIO
-> cache preview metadata Redis
-> return preview
-> if fail: return placeholder + degraded=true
```

Circuit breaker:

| State | Ý nghĩa |
|---|---|
| closed | gọi provider bình thường |
| open | bỏ qua provider, dùng cache/placeholder |
| half-open | thử lại có kiểm soát |

Rule:

```text
provider 429/5xx > 3 lần -> open 60s
sau cooldown -> half-open
success -> closed
fail -> open tiếp
```

Giữ SSRF guard hiện có trong URL validation.

## Hợp đồng API

Giữ API hiện tại, có thể bổ sung field.

```http
GET /v1/zones/{id}/imagery/latest
```

Response:

```json
{
  "scene_id": "S2_A01_2026_05_09",
  "rgb_url": "/v1/imagery/preview/S2_A01_2026_05_09?mode=rgb",
  "ndvi_url": "/v1/imagery/preview/S2_A01_2026_05_09?mode=ndvi",
  "signed_url": "https://minio/...",
  "acquisition_time": "2026-05-09T00:00:00Z",
  "cloud_cover": 18.5,
  "source": "sentinel2",
  "stale": false,
  "degraded": false,
  "trace_id": "..."
}
```

```http
GET /v1/zones/{id}/imagery/history?limit=10
```

Response:

```json
{
  "items": [
    {
      "scene_id": "...",
      "rgb_url": "...",
      "ndvi_url": "...",
      "acquisition_time": "...",
      "cloud_cover": 18.5,
      "source": "sentinel2",
      "stale": false,
      "degraded": false
    }
  ],
  "trace_id": "..."
}
```

## Chiến lược DB/cache

Không dùng DB.

| Storage | Dùng cho |
|---|---|
| Redis | metadata scene, breaker state, preview manifest |
| MinIO | preview PNG, cached image artifacts |
| Memory | fallback local/dev |

Cache keys:

```text
imagery:latest:{zone_id}
imagery:history:{zone_id}:{limit}
imagery:scene:{scene_id}
imagery:preview:{scene_id}:{mode}
breaker:imagery:{provider}
```

## FE gọi

- `ZoneImageryPanel`: latest scene.
- `ImageryTimeline`: history lazy load.
- `ZoneMap`: overlay image URL theo mode RGB/NDVI.
- Cache URL trong session/query cache.

FE target:

```text
useQuery(['imagery','latest', zoneId])
useQuery(['imagery','history', zoneId, limit], enabled when timeline visible)
```

## UI/UX

- Skeleton khi fetch.
- Badge:
  - Fresh `< 12h`: xanh
  - Cloudy `> 30%`: vàng
  - Stale `> 24h`: đỏ
- Fallback placeholder nếu timeout.
- Toggle RGB/NDVI không refetch thừa.
- Timeline thumbnail lazy load.

## Nghiệm thu

- FE không gọi provider trực tiếp.
- Provider lỗi vẫn có placeholder/degraded flag.
- Circuit breaker mở sau 3 lỗi.
- Redis/MinIO down không làm trắng dashboard.
- Timeline load lazy, không request history trước khi cần.

---

# 5.3 AI Prediction & Uncertainty Gating

## Hiện tại

BE:

- `POST /v1/predict` qua gateway.
- Live mode gọi AI Serving `/internal/predict`.
- AI Serving load manifest, chạy ONNX, MC Dropout, post-process, explain attention.
- `PostProcessor` có calibration/EMA/degraded/uncertainty.

FE:

- Trigger prediction bằng button.
- Hiển thị `stress_prob`, `uncertainty`, `confidence_flag`, `degraded_mode`, `explanation`.
- Confirm bị chặn nếu uncertainty > 0.3.

## Mục tiêu upgrade

- Predict vẫn là chức năng duy nhất chạy model trực tiếp.
- Kết quả predict phải được cache Redis để downstream dùng.
- Backend phải enforce uncertainty gate, không chỉ FE.
- Không train lại model trong phase này.

## Thiết kế BE

Feature đề xuất:

```text
backend/features/prediction/
├── router.py
├── schemas.py
├── service.py
├── cache.py
└── policy.py
```

Flow:

```text
POST /v1/predict
-> validate zone/timestamp
-> Gateway PredictionService.forward_to_ai_serving()
-> AI Serving ONNX inference
-> PostProcessor calibration + EMA + modality check
-> return PredictResponse
-> PredictionCacheService.store_latest(zone_id, response)
-> publish ws/status event optional
```

Prediction policy:

```text
uncertainty > 0.30 -> confidence_flag=low, command_blocked=true
0.15 < uncertainty <= 0.30 -> confidence_flag=medium, require_ack=true
uncertainty <= 0.15 -> confidence_flag=high

degraded_mode=true -> require_ack=true, command_blocked unless manual override enabled
missing modality -> uncertainty += 0.15 hoặc policy degraded/conservative
```

Timeout fallback:

```text
ONNX MC Dropout > 500ms
-> fallback single pass
-> degraded_mode=true
-> confidence_flag=low
```

## Hợp đồng API

Giữ:

```http
POST /v1/predict
```

Input:

```json
{
  "zone_id": "A01",
  "timestamp": "2026-05-09T12:00:00Z",
  "model_version": null
}
```

Output:

```json
{
  "zone_id": "A01",
  "stress_prob": 0.72,
  "uncertainty": 0.18,
  "confidence_flag": "medium",
  "degraded_mode": false,
  "attention_weights": [0.01, 0.02],
  "explanation": [
    {"feature": "soil_moisture", "weight": 0.34, "direction": "low"}
  ],
  "model_version": "onnx-v1",
  "latency_ms": 421,
  "trace_id": "..."
}
```

Có thể bổ sung field backend gate:

```json
{
  "safety": {
    "command_blocked": false,
    "require_ack": true,
    "reason": "medium_uncertainty"
  }
}
```

Nếu chưa muốn đổi schema, safety tính ở FE/command service.

## Chiến lược DB/cache

Không lưu DB phase này.

Redis:

```text
pred:{zone_id}:latest TTL 10m
pred:{zone_id}:{timestamp_bucket} TTL 30m
```

Payload cache:

- full PredictResponse
- created_at
- source: live/demo/degraded
- trace_id

Audit:

- JSON stdout.
- Fluentbit/file rotate sau.

## FE gọi

- `useMutation(predict)` khi user click.
- Optional auto-predict khi zone selected nếu product muốn.
- Store latest result vào Zustand `currentPrediction` hoặc mutation cache.
- Retry 1 lần.

## UI/UX

- Gauge stress 0-100%.
- Uncertainty badge:
  - `< 0.15`: High confidence / xanh
  - `0.15-0.30`: Medium / vàng
  - `> 0.30`: Low / đỏ
- `degraded_mode=true`: banner:

```text
Dữ liệu không đầy đủ, kết quả mang tính tham khảo.
```

- Tooltip XAI top-3 features.
- Nếu demo trace: banner rõ `Backend unavailable. Showing local demo result.`

## Nghiệm thu

- Predict live lưu Redis latest.
- Predict timeout trả degraded đúng.
- Uncertainty > 0.3 làm command bị block cả BE và FE.
- Missing modality tăng uncertainty/đưa degraded mode.
- Log có `trace_id`, `zone_id`, `stress_prob`, `uncertainty`, `latency_ms`.

---

# 5.4 Recommendation & Decision Engine

## Hiện tại

BE:

- `POST /v1/recommend` có sẵn.
- `evaluate_decision()` là pure function.
- Rule order đã có:
  - rain override
  - uncertainty/degraded gate
  - critical stress
  - moderate stress
  - early watch
  - healthy range

FE:

- Gọi recommend sau predict.
- Hiển thị action, volume, reason.

## Mục tiêu upgrade

- Recommendation không chạy model.
- Recommendation dùng output model gián tiếp.
- Có thể đọc prediction từ Redis cache để giảm FE phải gửi payload dài.
- Rule engine decoupled khỏi latency predict.
- Kết quả recommendation sinh alert nếu cần.

## Thiết kế BE

Feature đề xuất:

```text
backend/features/recommendation/
├── router.py
├── schemas.py
├── service.py
└── policy.py
```

Flow mode 1, giữ contract cũ:

```text
POST /v1/recommend
-> FE gửi prediction/telemetry/weather
-> RecommendationService.evaluate()
-> Decision Engine evaluate_decision()
-> cache decision latest
-> maybe publish alert event
```

Flow mode 2, từ cache:

```text
POST /v1/recommend/from-cache
-> body {zone_id}
-> load pred:{zone_id}:latest
-> load telemetry/weather mock/latest
-> evaluate_decision()
-> cache decision latest
-> publish alert event if action != no_irrigation
```

Không phá contract cũ.

## Hợp đồng API

Giữ:

```http
POST /v1/recommend
```

Input hiện tại:

```json
{
  "zone_id": "A01",
  "prediction": {...},
  "telemetry": {...},
  "weather": {...}
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

Thêm API optional:

```http
POST /v1/recommend/from-cache
```

Input:

```json
{
  "zone_id": "A01",
  "prediction_id": null
}
```

Miss cache:

```http
409 Conflict
```

```json
{
  "error_code": "PREDICTION_CACHE_MISS",
  "message": "No recent prediction found for zone",
  "trace_id": "...",
  "timestamp": "..."
}
```

## Chiến lược DB/cache

Redis:

```text
decision:{zone_id}:latest TTL 10m
```

Không DB phase này.

## FE gọi

- Sau predict success: gọi `POST /v1/recommend` hoặc `from-cache` nếu BE đã có.
- Nếu `require_ack=true`: bật state `ackNeeded`.
- Confirm disabled đến khi user tick xác nhận.

## UI/UX

Card recommendation:

- icon rõ:
  - tưới
  - giữ
  - bỏ qua do mưa
- reason tooltip.
- checkbox:

```text
Tôi đã xác nhận điều kiện thực địa
```

- Nếu `uncertainty > 0.3`: action là HOLD, không cho confirm.

## Nghiệm thu

- Recommendation không gọi model.
- Cache miss trả lỗi rõ.
- Rain override > 15mm/3h luôn no_irrigation.
- Uncertainty > 0.3 luôn hold.
- Decision latest lưu Redis.
- Alert event tạo khi action cần chú ý.

---

# 5.5 Alert Feed & Telegram Push

## Hiện tại

- `GET /v1/zones/{id}/alerts` đã có.
- FE poll alerts 30s.
- Chưa có ack API đầy đủ.
- Chưa có Telegram worker.
- Chưa có Redis Stream lifecycle.

## Mục tiêu upgrade

Alert lifecycle:

```text
open -> notified -> acknowledged -> resolved
```

Alert source:

- prediction high stress
- recommendation action != no_irrigation
- uncertainty high
- degraded data
- stale imagery
- provider/circuit breaker failure

## Thiết kế BE

Feature đề xuất:

```text
backend/features/alerts/
├── router.py
├── schemas.py
├── service.py
├── stream.py
├── telegram_worker.py
└── lifecycle.py
```

Redis structures:

```text
alerts:events                # Redis Stream
alerts:open                  # sorted/set/list open IDs
alert:{alert_id}             # Redis Hash metadata
alerts:zone:{zone_id}:open   # zone index
```

Alert event payload:

```json
{
  "id": "alert_...",
  "zone_id": "A01",
  "type": "irrigation_required",
  "severity": "moderate",
  "status": "open",
  "reason": "stress high and moisture low",
  "created_at": "2026-05-09T12:00:00Z",
  "trace_id": "...",
  "telegram_sent": false
}
```

Telegram worker:

```text
Redis Stream consumer group alert-monitor
-> read alert events
-> filter severity moderate/critical
-> call Telegram Bot API
-> store msg_id
-> update alert status notified
-> publish WS event system:alerts
```

Idempotency:

```text
alert_dedupe:{zone_id}:{type}:{time_bucket}
```

## Hợp đồng API

```http
GET /v1/zones/{id}/alerts
```

Response:

```json
{
  "items": [
    {
      "id": "alert_123",
      "type": "irrigation_required",
      "severity": "moderate",
      "status": "notified",
      "reason": "stress high and moisture low",
      "created_at": "2026-05-09T12:00:00Z",
      "telegram_sent": true
    }
  ],
  "trace_id": "..."
}
```

Thêm:

```http
POST /v1/alerts/{id}/ack
```

Response:

```json
{
  "id": "alert_123",
  "status": "acknowledged",
  "resolved_at": null,
  "trace_id": "..."
}
```

Optional resolve:

```http
POST /v1/alerts/{id}/resolve
```

## Chiến lược DB/cache

Phase này không DB.

- Redis Stream: queue/events.
- Redis Hash: metadata.
- JSON stdout: audit.
- File/Fluentbit later.

## FE gọi

- Poll 30s giữ như fallback.
- Nếu WebSocket có: subscribe `system:alerts`.
- `AlertFeed` render list.
- Ack button gọi `POST /v1/alerts/{id}/ack`.

## UI/UX

- Feed dọc panel phải hoặc dropdown.
- Severity colors:
  - critical: đỏ
  - moderate: cam
  - watch: vàng
- Badge Telegram nếu đã push.
- Click alert auto-pan map tới zone.
- Ack không xóa ngay critical alert; collapse với badge acknowledged.

## Nghiệm thu

- Recommendation tạo alert event khi cần.
- Worker gửi Telegram 1 lần/alert.
- Ack API đổi status đúng.
- FE nhận alert qua poll hoặc WS.
- Alert duplicate được dedupe.

---

# 5.6 Real-time Sync WebSocket

## Hiện tại

- Backend có `/ws/updates`.
- FE có `getWsUrl()` nhưng dashboard chưa dùng thật.
- Polling 30s vẫn là cơ chế chính cho alerts.

## Mục tiêu upgrade

Realtime pipeline:

```text
Service event
-> Redis Pub/Sub
-> Gateway WebSocket manager
-> FE useWebSocket
-> Zustand/React Query update
```

## Thiết kế BE

Feature đề xuất:

```text
backend/features/websocket/
├── router.py
├── manager.py
├── redis_subscriber.py
└── schemas.py
```

Channels:

```text
ws:broadcast
ws:zone:{zone_id}
system:alerts
system:health
```

Event contract:

```json
{
  "event": "zone_update",
  "payload": {
    "zone_id": "A01",
    "prediction": null,
    "alerts": []
  },
  "ts": "2026-05-09T12:00:00Z",
  "trace_id": "..."
}
```

Supported events:

| Event | Ý nghĩa |
|---|---|
| `zone_update` | status/prediction/decision đổi |
| `alert_opened` | alert mới |
| `alert_acknowledged` | alert được ack |
| `imagery_updated` | imagery mới/stale changed |
| `system_health` | readiness/degraded |
| `command_updated` | command status đổi |

PING/PONG:

```text
server ping every 30s
client pong hoặc reconnect
```

## Hợp đồng API

```http
WebSocket /ws/updates
```

Client subscribe message:

```json
{
  "type": "subscribe",
  "zones": ["A01"],
  "channels": ["system:alerts", "system:health"]
}
```

Server ack:

```json
{
  "event": "subscription_ack",
  "payload": {"zones": ["A01"]},
  "ts": "..."
}
```

## Chiến lược DB/cache

Không DB.

Redis Pub/Sub thuần.

## FE gọi

Hook:

```text
frontend/src/lib/realtime/useWebSocket.ts
```

Behavior:

- connect khi dashboard mount.
- subscribe selected zone.
- reconnect exponential:
  - 1s
  - 2s
  - 4s
  - max 30s
- parse event.
- invalidate React Query keys:
  - zone status
  - alerts
  - imagery
- update Zustand ws status.

## UI/UX

Header connection pill:

- Live
- Reconnecting
- Offline, using polling

Toast ngắn khi alert mới.

Polling fallback vẫn giữ.

## Nghiệm thu

- WS connect/reconnect ổn.
- Alert mới broadcast tới FE.
- Zone update invalidates correct query keys.
- WS down không làm dashboard lỗi.
- Không leak token qua URL trong production nếu chưa có chiến lược auth an toàn.

---

# 5.7 System Stability & Docker/Stub/Auth Fix

## Hiện tại

- Docker/config có nhưng cần healthcheck mạnh hơn.
- Stub/demo fallback nhiều.
- Production guard đã có một phần.
- 401 dev/admin gây cản trở test.

## Mục tiêu upgrade

- Local/dev chạy mượt, không 401 do thiếu admin.
- Production không cho stub/auth bypass.
- Docker biết service healthy trước khi gateway phụ thuộc.
- API error contract thống nhất.
- FE có degradation banner, không blank screen.

## Thiết kế BE

Config flags:

```text
APP_ENV=development|demo|production
AUTH_REQUIRED=false for dev/demo
DEV_AUTH_BYPASS_ROLE=admin|operator|viewer
ALLOW_STUBS=true only dev/demo
GATEWAY_MODE=live|stub
WS_REQUIRE_AUTH=false for dev/demo
```

Production guards:

```text
if APP_ENV=production and AUTH_REQUIRED=false -> fail startup
if APP_ENV=production and DEV_AUTH_BYPASS_ROLE set -> fail startup
if APP_ENV=production and GATEWAY_MODE=stub -> fail startup
if APP_ENV=production and ALLOW_STUBS=true -> fail startup
```

Auth bypass behavior:

```text
require_role()
-> if AUTH_REQUIRED=false and APP_ENV != production
-> return dev claims with role DEV_AUTH_BYPASS_ROLE
-> else validate token normally
```

Docker healthcheck:

| Service | Liveness | Readiness |
|---|---|---|
| gateway | `/v1/healthz` | `/v1/readyz` |
| ai-serving | `/healthz` | `/readyz` |
| decision | `/healthz` | `/readyz` |
| ingestion | `/healthz` | `/readyz` |
| redis | `redis-cli ping` | `redis-cli ping` |
| minio | `/minio/health/live` | `/minio/health/ready` |

Error contract:

```json
{
  "error_code": "SERVICE_UNAVAILABLE",
  "message": "Service temporarily unavailable",
  "trace_id": "...",
  "timestamp": "2026-05-09T12:00:00Z"
}
```

## Hợp đồng API

`GET /v1/readyz` mở rộng:

```json
{
  "status": "ready",
  "dependencies": {
    "redis": "ok",
    "minio": "ok",
    "ai_serving": "ok",
    "ingestion": "ok",
    "weather": "degraded"
  },
  "mode": "live",
  "auth_required": false,
  "trace_id": "..."
}
```

## Chiến lược DB/cache

Không DB.

Readiness kiểm tra:

- Redis ping.
- MinIO health nếu enabled.
- AI serving ready.
- DB only nếu feature cần DB thật.

## FE gọi

`apiRequest` bắt lỗi:

- 401:
  - nếu dev/demo auth bypass enabled: show setup warning, không silent fallback production.
  - nếu production: show auth required.
- 503/5xx:
  - fallback demo nếu dev mode cho phép.
  - degradation banner.

FE env:

```text
VITE_DEV_AUTH_BYPASS=true only dev/demo
VITE_ALLOW_DEMO_FALLBACK=true only dev/demo
```

## UI/UX

- Banner top:

```text
Dev auth bypass enabled. Not for production.
```

- Backend unavailable banner.
- Retry button.
- Use demo data button only dev/demo.
- No blank screen.

## Nghiệm thu

- Local dashboard/admin không 401 khi auth bypass bật.
- Production fail startup nếu bypass/stub bật.
- Docker compose waits service healthy.
- Error response không lộ stack trace.
- FE hiển thị degradation banner đúng.

---

## 6. Cơ chế bù trừ cho model hiện tại

Không train lại model trong phase này.

Bù trừ bằng policy runtime:

### 6.1 Uncertainty gating

```text
uncertainty > 0.30
-> force HOLD
-> disable confirm
-> backend command reject
-> require manual review
```

### 6.2 Missing modality

```text
modality_mask thiếu kênh
-> uncertainty += 0.15 hoặc degraded_mode=true
-> decision engine conservative mode
-> giảm volume 30% nếu vẫn tưới
```

### 6.3 Temporal smoothing

```text
EMA alpha = 0.6 trên 3 predict cuối
Nếu missing data -> alpha = 0.4
```

Mục tiêu:

- giảm flickering alert
- tránh action thay đổi quá nhanh giữa các lần predict

### 6.4 Timeout fallback

```text
ONNX > 500ms
-> dừng MC Dropout
-> single pass
-> degraded_mode=true
-> confidence_flag=low
```

### 6.5 Rain override

```text
rain_forecast_3h > 15mm
-> no_irrigation
-> bỏ qua stress_prob
```

---

## 7. Logging & Audit tối giản

Format:

```json
{
  "trace_id": "...",
  "service": "api_gateway",
  "zone_id": "A01",
  "event": "prediction_completed",
  "stress_prob": 0.72,
  "uncertainty": 0.18,
  "action": "light_irrigation",
  "latency_ms": 421,
  "degraded_mode": false,
  "timestamp": "2026-05-09T12:00:00Z"
}
```

Event cần log:

| Event | Fields quan trọng |
|---|---|
| `zone_registry_loaded` | zone_count, source, latency_ms |
| `imagery_latest_loaded` | zone_id, source, stale, degraded |
| `imagery_breaker_opened` | provider, fail_count, cooldown |
| `prediction_started` | zone_id, model_version |
| `prediction_completed` | stress_prob, uncertainty, latency_ms, degraded |
| `recommendation_created` | action, volume_mm, reason |
| `command_rejected` | reason, uncertainty, degraded |
| `command_created` | command_id, action, volume_mm |
| `alert_opened` | alert_id, type, severity |
| `alert_notified` | alert_id, telegram_msg_id |
| `alert_acknowledged` | alert_id, user/source |
| `ws_connected` | connection_id, role/dev_mode |
| `ws_disconnected` | connection_id, reason |

Storage phase 1:

- stdout JSON single-line.
- File rotate/Fluentbit sau.
- Redis Hash cho alert lifecycle.

---

## 8. Kế hoạch triển khai theo thứ tự

## Phase 0: Chốt contract và guard dev/demo

Mục tiêu:

- Loại bỏ cản trở 401 trong local/dev/demo.
- Khóa không cho bypass lọt production.

BE:

- Thêm/chuẩn hóa `APP_ENV`, `AUTH_REQUIRED`, `DEV_AUTH_BYPASS_ROLE`, `ALLOW_STUBS`.
- `require_role()` trả dev claims khi auth disabled và không phải production.
- Production guard fail fast nếu stub/bypass bật.

FE:

- Thêm auth mode helper.
- Hiển thị banner dev auth bypass.
- Không fallback local demo cho 401 ở production.

API:

- Giữ nguyên path.
- Chuẩn hóa error contract.

Nghiệm thu:

- Local dashboard/admin không còn 401.
- Production config bật bypass thì app fail startup.

---

## Phase 1: Zone registry service + dashboard store

Mục tiêu:

- Chuẩn hóa zone source.
- FE state rõ ràng.

BE:

- Tạo `ZoneRegistryService`.
- Load GeoJSON/CSV khi startup.
- Cache memory + Redis optional.
- `/v1/zones` gọi service.

FE:

- Thêm Zustand `dashboardStore`.
- Store selected zone, imagery mode, ws status, ack local.
- Sync URL qua store.

Nghiệm thu:

- `/v1/zones` ổn định.
- URL `?zone=ID` valid/fallback đúng.
- Map/list chọn zone đồng bộ.

---

## Phase 2: Prediction cache + backend safety gate

Mục tiêu:

- Predict lưu latest cache.
- Command an toàn ở BE.

BE:

- Tạo `PredictionCacheService`.
- `/v1/predict` lưu Redis `pred:{zone_id}:latest`.
- Tạo safety policy chung.
- `/v1/commands` reject khi:
  - no latest prediction
  - `uncertainty > 0.30`
  - `degraded_mode=true` nếu chưa manual override/ack
  - local demo trace nếu production

FE:

- Tách mutation flow.
- Hiển thị lý do disable confirm.
- Degradation banner.

Nghiệm thu:

- High uncertainty bị chặn cả FE/BE.
- Predict timeout degraded đúng.
- Redis down vẫn có fallback memory/dev behavior rõ.

---

## Phase 3: Recommendation from cache + status aggregate

Mục tiêu:

- Recommendation decoupled predict latency.
- Zone status đọc từ cache tổng hợp thay vì build demo inline.

BE:

- Thêm `RecommendationService`.
- Optional `POST /v1/recommend/from-cache`.
- Cache decision latest `decision:{zone_id}:latest`.
- Tạo `ZoneStatusService` aggregate:
  - telemetry latest
  - prediction latest
  - decision latest
  - imagery latest
  - alert summary
  - weather cached

FE:

- Sau predict success gọi recommend.
- Nếu backend support from-cache thì dùng path mới.
- Status UI đọc consistent fields.

Nghiệm thu:

- Recommend không chạy model.
- Cache miss trả 409 rõ.
- Status phản ánh latest prediction/decision.

---

## Phase 4: Imagery proxy Redis/MinIO/circuit breaker

Mục tiêu:

- Imagery chịu lỗi tốt.
- Giảm render on-the-fly lặp lại.

BE:

- Thêm Redis metadata cache.
- Thêm MinIO preview storage.
- Thêm circuit breaker provider.
- Giữ placeholder fallback.
- Preserve SSRF guard.

FE:

- Timeline lazy load.
- Thumbnail `loading="lazy"`.
- Retry/empty state.
- Badge stale/cloudy/fresh.

Nghiệm thu:

- Provider lỗi 3 lần -> breaker open.
- Preview cache hit không render lại.
- Dashboard vẫn hiển thị placeholder khi upstream lỗi.

---

## Phase 5: Alert stream + Telegram worker + ack API

Mục tiêu:

- Alerts thành workflow vận hành thật.

BE:

- Redis Stream `alerts:events`.
- Redis Hash alert metadata.
- Worker Telegram.
- Ack API.
- Dedupe alert.

FE:

- `AlertFeed` component.
- Ack button.
- Badge telegram sent.
- Click alert pan map.

Nghiệm thu:

- Recommendation action tạo alert.
- Telegram gửi đúng một lần.
- Ack update trạng thái.
- Alert feed cập nhật qua poll/WS.

---

## Phase 6: WebSocket realtime sync

Mục tiêu:

- Dashboard cập nhật realtime.

BE:

- WebSocket manager.
- Redis Pub/Sub subscriber.
- PING/PONG.
- Event schema.

FE:

- `useWebSocket` hook.
- Reconnect exponential.
- Invalidate React Query keys khi event tới.
- Connection status pill.

Nghiệm thu:

- Alert mới xuất hiện không cần reload.
- Zone update refresh đúng query.
- WS drop thì reconnect, polling vẫn chạy.

---

## Phase 7: Refactor cấu trúc backend theo feature

Mục tiêu:

- Giảm god file.
- Chuẩn hóa cấu trúc dài hạn.

Target từ `Tai_cau_truc.md`:

```text
backend/
├── apps/
├── features/
└── platform/
```

Thứ tự refactor:

1. Tách health router.
2. Tách zones router/service.
3. Tách prediction router/service/cache.
4. Tách recommendation router/service.
5. Tách imagery router/service.
6. Tách alerts router/service.
7. Tách commands router/service.
8. Tách websocket router/manager.
9. Di chuyển shared infra từ `core` sang `platform` bằng compatibility imports.
10. Tách schemas theo feature sau cùng.

Nghiệm thu:

- Route cũ vẫn hoạt động.
- Tests cũ pass.
- `api_gateway/main.py` chỉ còn app wiring/middleware/include router.
- Không còn thêm `sys.path.insert` mới.

---

## 9. Checklist 10 ngày đề xuất

| Ngày | Trọng tâm | Tiêu chí nghiệm thu |
|---|---|---|
| 1 | Auth dev bypass + production guard + error contract | Local không 401; prod fail nếu bypass/stub bật |
| 2 | Docker healthcheck + readiness dependencies | Compose start ổn; readyz báo dependency rõ |
| 3 | ZoneRegistryService + Redis/memory cache | `/v1/zones` chuẩn; FE zone sync URL |
| 4 | Prediction cache + safety policy | Predict cache Redis; command bị chặn khi unc cao |
| 5 | Recommendation from-cache + decision latest | Recommend không phụ thuộc FE gửi full prediction |
| 6 | ZoneStatusService aggregate | Status đọc latest pred/decision/imagery/alert |
| 7 | Imagery Redis/MinIO/cache + circuit breaker | Provider lỗi vẫn không blank UI |
| 8 | Alert Redis Stream + Telegram worker + ack | Alert lifecycle chạy được |
| 9 | WebSocket manager + FE useWebSocket | Alert/status realtime update |
| 10 | E2E, fallback validation, UI polish, docs | Zone -> Predict -> Recommend -> Alert -> WS trơn tru |

---

## 10. Rủi ro và giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Big-bang refactor làm gãy import/tests | Cao | Strangler pattern, giữ compatibility imports |
| Auth bypass lọt production | Cao | Production guard fail startup + tests |
| Redis thành single point of failure | Trung bình | Memory fallback cho dev/demo; readiness degraded |
| MinIO chưa sẵn làm imagery chết | Trung bình | Placeholder/local demo degraded flag |
| Model sai lệch cao | Cao | Uncertainty gate + EMA + rain override + backend command reject |
| Alert Telegram duplicate | Trung bình | Idempotency key + Redis dedupe |
| WebSocket leak connection | Trung bình | Manager cleanup on disconnect + ping/pong timeout |
| Stub che lỗi live integration | Cao | Hard-disable stub trong production; banner demo rõ |
| Circuit breaker quá nhạy | Thấp/Trung bình | Config threshold/cooldown, half-open retry |
| FE quá nhiều banner gây mệt | Thấp | Gom degradation signals thành 1 banner expandable |

---

## 11. Danh sách module/file nên tạo

### Backend

```text
backend/features/zones/registry.py
backend/features/zones/status_service.py
backend/features/prediction/cache.py
backend/features/prediction/policy.py
backend/features/recommendation/service.py
backend/features/imagery/service.py
backend/features/imagery/persistence.py
backend/features/imagery/circuit_breaker.py
backend/features/alerts/service.py
backend/features/alerts/stream.py
backend/features/alerts/telegram_worker.py
backend/features/websocket/manager.py
backend/features/websocket/redis_subscriber.py
backend/platform/cache.py
backend/platform/storage.py
backend/platform/runtime_guard.py
```

### Frontend

```text
frontend/src/features/dashboard/store/dashboardStore.ts
frontend/src/features/dashboard/hooks/useDashboardQueries.ts
frontend/src/features/dashboard/hooks/usePredictionFlow.ts
frontend/src/features/dashboard/hooks/useDegradationSignals.ts
frontend/src/lib/realtime/useWebSocket.ts
frontend/src/lib/realtime/types.ts
frontend/src/components/dashboard/DegradationBanner.tsx
frontend/src/components/dashboard/AlertFeed.tsx
frontend/src/lib/auth/mode.ts
```

---

## 12. Test plan

### Backend unit tests

- Zone registry load/validate/cache.
- Imagery circuit breaker transitions.
- Prediction cache write/read/invalidate.
- Safety policy:
  - high uncertainty block
  - degraded mode block/ack
  - missing modality conservative
- Recommendation from cache hit/miss.
- Alert lifecycle.
- Telegram worker idempotency.
- WebSocket manager subscribe/fanout.
- Runtime guard production stub/bypass fail.

### Backend integration tests

- `/v1/zones` returns normalized response.
- `/v1/predict` stores Redis latest.
- `/v1/recommend/from-cache` uses cached prediction.
- `/v1/commands` rejects unsafe prediction.
- `/v1/zones/{id}/imagery/latest` falls back on provider fail.
- `/v1/alerts/{id}/ack` updates status.
- `/v1/readyz` reports dependencies.
- local/dev auth bypass prevents 401.

### Frontend tests

- Store selection updates URL/state.
- Prediction flow disables confirm with high uncertainty.
- Degradation banner renders demo/degraded/stale/ws/auth states.
- AlertFeed ack behavior.
- WebSocket reconnect updates status.
- Imagery timeline lazy load.

### E2E tests

Golden path:

```text
Open /dashboard
-> load zones
-> select zone
-> load imagery latest/history
-> run predict
-> run recommend
-> receive alert
-> acknowledge alert
-> websocket updates dashboard
```

Failure path:

```text
Backend 503 -> fallback banner
Imagery provider timeout -> placeholder + stale/degraded badge
Predict uncertainty > 0.3 -> command disabled/rejected
WS disconnect -> reconnecting pill + polling fallback
401 dev bypass -> no blocker in local/demo
```

---

## 13. Kết luận

Hệ thống hiện tại đã có nền chức năng khá đầy đủ, đặc biệt là:

- dashboard flow
- imagery flow
- prediction ML serving
- recommendation rule engine
- telemetry skeleton
- alerts feed
- websocket endpoint

Nhưng hệ thống còn ở trạng thái **demo-operational**, chưa phải **stable operational loop**.

Phiên upgrade nên tập trung vào:

1. Bypass auth dev/demo có guard production.
2. Redis làm trục cache/realtime/alert.
3. Backend enforce safety gate, không giao hết cho FE.
4. MinIO/circuit breaker cho imagery.
5. Alert lifecycle + Telegram push.
6. WebSocket realtime sync.
7. Refactor backend theo feature sau khi behavior ổn.

Nếu làm theo thứ tự trên, hệ thống sẽ chuyển dần từ:

```text
stub/demo + fallback rời rạc
```

sang:

```text
stable operational loop + audit trace + realtime sync + safety gating
```

mà không cần train lại model trong phase này.
