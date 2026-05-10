# Kế hoạch tái cấu trúc backend theo chức năng

## Mục tiêu

Chuyển cấu trúc backend từ kiểu chia theo module kỹ thuật sang kiểu chia theo feature/domain.

Mục tiêu chính:

- Giảm file `main.py` quá lớn và quá nhiều trách nhiệm.
- Gom logic theo nghiệp vụ để dễ đọc, dễ mở rộng, dễ test.
- Tách rõ `app entrypoint`, `domain feature`, và `shared platform`.
- Giảm phụ thuộc vào `sys.path.insert(...)`.
- Cho phép refactor từng bước nhỏ, ít rủi ro, không làm gãy toàn bộ hệ thống.

---

## Hiện trạng backend

Hiện repo backend đang chia chủ yếu theo service kỹ thuật:

```text
backend/
├── api_gateway/        # public API app + clients
├── ai_serving/         # inference service
├── decision_engine/    # rule engine service
├── ingestion_service/  # telemetry ingest service
└── core/               # shared config/db/errors/schemas/security/imagery/weather
```

### Điểm yếu chính

- `backend/api_gateway/main.py` đang ôm quá nhiều trách nhiệm:
  - middleware
  - auth dependency
  - weather
  - imagery
  - alerts
  - zone registry
  - websocket
  - command endpoint
- `backend/core/schemas.py` đang là file gom gần như toàn bộ contract của nhiều domain khác nhau.
- Nhiều logic domain đang bị nhét vào `core/`, ví dụ:
  - `imagery.py`
  - `imagery_persistence.py`
  - `imagery_proxy.py`
  - `weather.py`
  - `zone_status_cache.py`
- Nhiều nơi đang dựa vào `sys.path.insert(...)`, dễ gây lỗi khi đổi cấu trúc thư mục.
- Test hiện phụ thuộc mạnh vào import path cũ như:
  - `api_gateway.main`
  - `core.schemas`
  - `decision_engine.main`

---

## Định hướng cấu trúc mới

Không nên bê nguyên ví dụ ShareCV, mà nên áp dụng phiên bản phù hợp với repo hiện tại.

### Cấu trúc target đề xuất

```text
backend/
├── apps/
│   ├── api_gateway/
│   │   ├── app.py
│   │   ├── lifespan.py
│   │   ├── dependencies.py
│   │   ├── middleware.py
│   │   └── clients/
│   │       ├── ai_client.py
│   │       ├── decision_client.py
│   │       └── ingestion_client.py
│   ├── ai_serving/
│   │   ├── app.py
│   │   ├── lifespan.py
│   │   ├── manifest_store.py
│   │   └── onnx_wrapper.py
│   ├── ingestion/
│   │   ├── app.py
│   │   └── service.py
│   └── decision/
│       ├── app.py
│       ├── service.py
│       └── alerts.py
├── features/
│   ├── health/
│   │   ├── router.py
│   │   └── schemas.py
│   ├── prediction/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── recommendation/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── telemetry/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── zones/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── registry.py
│   │   └── status_service.py
│   ├── imagery/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── persistence.py
│   │   └── preview.py
│   ├── weather/
│   │   ├── schemas.py
│   │   └── service.py
│   ├── alerts/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── commands/
│   │   ├── router.py
│   │   └── schemas.py
│   └── websocket/
│       ├── router.py
│       └── auth.py
├── platform/
│   ├── config.py
│   ├── db.py
│   ├── errors.py
│   ├── http_client.py
│   ├── logging.py
│   ├── rate_limit.py
│   └── security.py
└── __init__.py
```

---

## Nguyên tắc phân lớp

### 1. `apps/`
Chứa entrypoint của từng service.

Chỉ nên giữ:

- khởi tạo `FastAPI`
- `lifespan`
- middleware
- dependency wiring
- include router
- wiring client/service

Không nên để business logic lớn ở đây.

### 2. `features/`
Chứa code theo domain nghiệp vụ.

Ví dụ:

- prediction
- recommendation
- telemetry
- imagery
- zones
- alerts
- weather

Mỗi feature có thể chứa:

- `router.py`
- `schemas.py`
- `service.py`
- `repository.py` hoặc `persistence.py`
- helper nội bộ nếu cần

### 3. `platform/`
Chứa hạ tầng dùng chung, không gắn với 1 nghiệp vụ cụ thể.

Ví dụ:

- config
- db
- errors
- http client
- rate limit
- auth/security
- logging

---

## Mapping từ cấu trúc cũ sang cấu trúc mới

### Shared infrastructure

```text
backend/core/config.py              -> backend/platform/config.py
backend/core/db.py                  -> backend/platform/db.py
backend/core/errors.py              -> backend/platform/errors.py
backend/core/http_client.py         -> backend/platform/http_client.py
backend/core/logging.py             -> backend/platform/logging.py
backend/core/rate_limit.py          -> backend/platform/rate_limit.py
backend/core/security.py            -> backend/platform/security.py
```

### Schemas

```text
backend/core/schemas.py             -> split vào backend/features/*/schemas.py
```

### Domain logic

```text
backend/core/weather.py             -> backend/features/weather/service.py + schemas.py
backend/core/imagery.py             -> backend/features/imagery/service.py
backend/core/imagery_persistence.py -> backend/features/imagery/persistence.py
backend/core/imagery_proxy.py       -> backend/features/imagery/preview.py
backend/core/geospatial.py          -> backend/features/zones/geospatial.py hoặc backend/platform/geospatial.py
backend/core/zone_status_cache.py   -> backend/features/zones/status_cache.py
```

### Service apps

```text
backend/decision_engine/main.py         -> backend/apps/decision/app.py + backend/apps/decision/service.py
backend/decision_engine/alert_engine.py -> backend/features/alerts/service.py

backend/ingestion_service/main.py       -> backend/apps/ingestion/app.py + backend/features/telemetry/service.py

backend/ai_serving/main.py              -> backend/apps/ai_serving/app.py + backend/apps/ai_serving/manifest_store.py
backend/ai_serving/onnx_wrapper.py      -> backend/apps/ai_serving/onnx_wrapper.py

backend/api_gateway/main.py             -> backend/apps/api_gateway/app.py + feature routers
backend/api_gateway/clients/*           -> backend/apps/api_gateway/clients/*
```

---

## Kế hoạch triển khai theo phase

Không làm kiểu big-bang. Làm từng phase nhỏ để dễ kiểm soát rủi ro.

---

### Phase 0 — Chốt baseline trước refactor

Mục tiêu: biết trạng thái hiện tại trước khi đụng cấu trúc.

Việc cần làm:

1. Chạy test backend hiện có.
2. Ghi nhận test nào đang pass, test nào đang fail.
3. Không move file trước khi biết baseline.

Lệnh gợi ý:

```bash
pytest tests/backend
```

Kết quả mong muốn:

- Có ảnh chụp trạng thái test hiện tại.
- Có mốc so sánh sau mỗi phase.

---

### Phase 1 — Chuẩn hóa package/import trước khi move

Mục tiêu: giảm rủi ro vỡ import khi đổi cây thư mục.

Việc cần làm:

1. Chuẩn hóa import path theo package `backend`.
2. Giảm phụ thuộc vào `sys.path.insert(...)`.
3. Thiết lập import mới dần dần.
4. Giữ compatibility layer tạm thời cho path cũ.

Ví dụ import đích:

```python
from backend.platform.config import get_settings
from backend.features.prediction.schemas import PredictRequest
```

Trong giai đoạn chuyển tiếp có thể giữ file cũ re-export từ file mới, ví dụ:

```text
backend/core/config.py
backend/core/schemas.py
```

Lợi ích:

- Test cũ vẫn chạy được.
- Refactor từng bước không làm nổ toàn bộ import graph.

---

### Phase 2 — Tách `platform/` khỏi `core/`

Mục tiêu: bóc hạ tầng dùng chung ra khỏi domain logic.

Các file nên move trước:

```text
config.py
db.py
errors.py
http_client.py
logging.py
rate_limit.py
security.py
```

Đích đến:

```text
backend/platform/
```

Việc cần làm:

1. Tạo package `backend/platform/`.
2. Move hoặc copy từng file sang đó.
3. Update import trong các service.
4. Nếu cần, giữ re-export tạm ở `backend/core/*`.

Lưu ý:

- Phase này chưa động vào business logic.
- Mục tiêu chỉ là chia lại lớp hạ tầng.

---

### Phase 3 — Tách `schemas.py` theo feature

Mục tiêu: phá file contract lớn thành nhiều schema theo domain.

Tách từ `backend/core/schemas.py` thành:

```text
features/prediction/schemas.py
  - PredictRequest
  - PredictResponse
  - FeatureImportance
  - ConfidenceFlag

features/recommendation/schemas.py
  - RecommendRequest
  - IrrigationDecision
  - RecAction

features/telemetry/schemas.py
  - TelemetryMeasurement
  - TelemetryIngestRequest
  - TelemetryIngestResponse

features/commands/schemas.py
  - CommandStatus
  - IrrigationCommandRequest
  - IrrigationCommandResponse

features/zones/schemas.py
  - ZoneRegistryEntry
  - ZoneListItemResponse
  - ZoneListResponse
  - ZoneStatusResponse

features/imagery/schemas.py
  - ImagerySummary
  - ImageryScene
  - ImagerySceneCollection

features/alerts/schemas.py
  - AlertSummary
  - AlertRecord
  - AlertFeedResponse

features/health/schemas.py
  - HealthResponse
```

Trong giai đoạn chuyển tiếp:

- giữ `backend/core/schemas.py` làm lớp re-export
- chỉ remove khi toàn bộ import cũ đã được thay xong

Lợi ích:

- Mỗi feature tự sở hữu contract của nó.
- Dễ tìm schema hơn.
- Giảm coupling giữa các domain.

---

### Phase 4 — Tách `api_gateway/main.py` thành app + routers

Mục tiêu: làm `main.py` mỏng, business logic đi về feature.

Cấu trúc gợi ý:

```text
backend/apps/api_gateway/app.py
backend/apps/api_gateway/lifespan.py
backend/apps/api_gateway/middleware.py
backend/apps/api_gateway/dependencies.py

backend/features/health/router.py
backend/features/prediction/router.py
backend/features/recommendation/router.py
backend/features/telemetry/router.py
backend/features/zones/router.py
backend/features/imagery/router.py
backend/features/alerts/router.py
backend/features/commands/router.py
backend/features/websocket/router.py
```

`app.py` chỉ nên làm việc như:

- tạo `FastAPI`
- add middleware
- setup state/lifespan
- include routers

Ví dụ:

```python
app = FastAPI(...)
app.include_router(health_router)
app.include_router(prediction_router, prefix="/v1")
app.include_router(recommendation_router, prefix="/v1")
```

Lợi ích:

- Route theo domain rõ ràng.
- `api_gateway` dễ mở rộng hơn.
- Mỗi router test độc lập hơn.

---

### Phase 5 — Move domain service khỏi `core/` và `main.py`

Mục tiêu: gom logic về đúng feature.

#### Zones

Tách khỏi `api_gateway/main.py`:

```text
load_zone_registry()  -> features/zones/registry.py
load_zone_feature()   -> features/zones/registry.py
get_zone_bbox()       -> features/zones/registry.py
build_zone_status()   -> features/zones/status_service.py
```

#### Weather

```text
fetch_weather_for_zone() -> features/weather/service.py
extract_rain_3h()        -> features/weather/service.py
```

#### Alerts

```text
build_alerts()                  -> features/alerts/service.py
build_zone_alert_records()      -> features/alerts/service.py
```

#### Imagery

```text
core/imagery.py             -> features/imagery/service.py
core/imagery_persistence.py -> features/imagery/persistence.py
core/imagery_proxy.py       -> features/imagery/preview.py
```

Lợi ích:

- Logic domain nằm gần router/schema của chính nó.
- `core/` cũ không còn vai trò “sọt rác mọi thứ”.

---

### Phase 6 — Tách microservice apps rõ hơn

Mục tiêu: mỗi app chỉ giữ entrypoint, logic chuyển ra service.

#### Decision service

```text
apps/decision/app.py
apps/decision/service.py
features/alerts/service.py
```

#### Ingestion service

```text
apps/ingestion/app.py
features/telemetry/service.py
```

#### AI serving

```text
apps/ai_serving/app.py
apps/ai_serving/manifest_store.py
apps/ai_serving/onnx_wrapper.py
```

Việc cần làm:

- Tách logic xử lý request khỏi file `main.py`
- Giữ `app.py` gọn, chủ yếu wiring

---

### Phase 7 — Cập nhật test theo path mới

Mục tiêu: chuyển test sang import feature/app mới.

Ví dụ:

```python
from api_gateway.main import app
```

đổi thành:

```python
from backend.apps.api_gateway.app import app
```

Ví dụ khác:

```python
from decision_engine.main import evaluate_decision
```

đổi thành:

```python
from backend.apps.decision.service import evaluate_decision
```

Schema test:

```python
from core.schemas import PredictResponse
```

đổi thành:

```python
from backend.features.prediction.schemas import PredictResponse
```

Lưu ý:

- Cập nhật test theo từng phase, không dồn cuối cùng nếu lượng đổi quá lớn.
- Nếu cần vẫn giữ compatibility layer tới khi toàn bộ test xanh.

---

### Phase 8 — Xóa compatibility layer cũ

Mục tiêu: dọn phần cũ sau khi mọi thứ ổn định.

Các đường dẫn có thể remove ở cuối:

```text
backend/core/*
backend/api_gateway/main.py
backend/decision_engine/main.py
backend/ingestion_service/main.py
backend/ai_serving/main.py
```

Chỉ xóa khi:

- test pass
- Docker/CI đã update import path và app path
- không còn consumer nào dùng path cũ

---

## Cập nhật Docker / runtime

Sau khi đổi app path, cần update target chạy uvicorn trong Dockerfile hoặc script deploy.

Ví dụ:

```dockerfile
CMD ["uvicorn", "backend.apps.api_gateway.app:app", ...]
CMD ["uvicorn", "backend.apps.ai_serving.app:app", ...]
CMD ["uvicorn", "backend.apps.ingestion.app:app", ...]
CMD ["uvicorn", "backend.apps.decision.app:app", ...]
```

Nếu không update phần này, app sẽ gãy dù code đã refactor đúng.

---

## Rủi ro chính cần kiểm soát

### 1. `sys.path.insert(...)`
Hiện tại nó đang che nhiều vấn đề package/import.

Nếu bỏ quá sớm:

- test gãy
- script gãy
- migration gãy

Cách xử lý:

- chuẩn hóa import trước
- giữ shim/re-export tạm thời

### 2. `core.schemas` đang là single source of truth
Nếu tách ẩu có thể gây:

- enum bị duplicate
- circular import
- contract bị lệch

Cách xử lý:

- tách theo nhóm rõ ràng
- giữ compatibility layer trong 1–2 phase đầu

### 3. `api_gateway.main` đang giữ nhiều app state
Nếu tách router mà không giữ cách truy cập state ổn định, dễ lỗi runtime.

Cách xử lý:

- tiếp tục lấy qua `request.app.state`
- không tạo global state mới bừa bãi

### 4. Dockerfile / deploy path
Move app xong mà không sửa command chạy service sẽ fail boot.

### 5. Test hiện phụ thuộc path cũ nhiều
Nếu rename một lần quá mạnh, chi phí sửa test sẽ rất lớn.

Cách xử lý:

- dùng compatibility layer
- đổi import test theo phase

---

## Thứ tự PR gợi ý

1. `refactor: add backend platform package`
2. `refactor: split backend schemas by feature`
3. `refactor: extract gateway routers`
4. `refactor: move imagery and weather features`
5. `refactor: move decision and telemetry services`
6. `refactor: update app entrypoints and docker commands`
7. `test: migrate backend imports to feature layout`
8. `chore: remove legacy backend compatibility modules`

---

## Khuyến nghị triển khai thực tế

Nên làm trước **Phase 1 → Phase 3**:

- chuẩn hóa import
- tạo `platform/`
- tách `schemas` theo feature

Đây là phần nền móng, ít rủi ro nhất.

Sau khi xong mới sang:

- tách router từ `api_gateway`
- move domain services
- đổi app entrypoints
- dọn lớp compatibility cũ

### Khuyến nghị quan trọng

Không nên move toàn bộ thư mục backend trong một lần.

Cách an toàn hơn:

- tạo package mới song song
- move theo lát cắt nhỏ
- test sau mỗi lát cắt
- chỉ xóa path cũ khi path mới đã ổn định

---

## Kết luận

Hướng tái cấu trúc phù hợp nhất cho backend hiện tại là:

- `apps/` cho entrypoint từng service
- `features/` cho domain nghiệp vụ
- `platform/` cho hạ tầng dùng chung

Cách đi tốt nhất là refactor theo nhiều phase nhỏ, không big-bang.

Nếu triển khai đúng thứ tự, hệ thống sẽ đạt được:

- cấu trúc rõ hơn
- business logic gần domain hơn
- test dễ bảo trì hơn
- mở rộng feature mới dễ hơn
- giảm rủi ro gãy import/runtime khi codebase lớn dần

---

# Kế hoạch tái cấu trúc frontend theo chức năng

## Mục tiêu

Điều chỉnh frontend theo mô hình chức năng giống mẫu anh đưa: `app`, `modules`, `common`, `config`, `interfaces`, `lib`.

Mục tiêu chính:

- Tổ chức code theo màn hình/chức năng nghiệp vụ trong `modules/`.
- Giữ `app/` chỉ làm app shell, route entry, layout, provider.
- Gom thành phần dùng chung vào `common/`.
- Gom cấu hình hệ thống vào `config/`.
- Tách interface/type theo domain để tránh file type khổng lồ.
- Giữ cấu trúc dễ mở rộng nếu sau này chuyển sang Next.js App Router hoặc giữ Vite React.

---

## Định hướng theo mẫu tham khảo

Mẫu anh đưa có tư duy chính:

```text
app/          # layout, page, provider, route group
common/       # apis, components, constants, helpers, interfaces, types dùng chung
config/       # constant, i18n, react-query
interfaces/   # interface theo domain nghiệp vụ
lib/          # state/store/tooling cấp thấp
modules/      # từng chức năng/màn hình nghiệp vụ
public/       # tài nguyên tĩnh
```

Áp dụng vào repo hiện tại, FE nên đi theo hướng:

- `modules/` thay cho `features/`.
- `common/` thay cho `components/shared` và một phần `lib` dùng chung.
- `config/` thay cho config rải rác trong `lib/i18n`, map config, env config.
- `interfaces/` thay cho `lib/api/types.ts` đang gom nhiều domain.
- `app/` giữ router/provider/main/layout cấp ứng dụng.

---

## Hiện trạng frontend hiện tại

Repo hiện tại đang có:

```text
frontend/src/
├── app/
│   ├── providers.tsx
│   ├── router.tsx
│   └── router.test.tsx
├── components/
│   ├── dashboard/
│   │   ├── DataFusionPanel.tsx
│   │   ├── ImageryTimeline.tsx
│   │   ├── ZoneImageryPanel.tsx
│   │   ├── ZoneMap.tsx
│   │   └── ZoneOverlay.tsx
│   └── shared/
│       ├── LanguageToggle.tsx
│       └── ThemeToggle.tsx
├── features/
│   ├── admin/
│   │   └── pages/
│   │       ├── AdminPage.tsx
│   │       └── AdminPage.test.tsx
│   ├── dashboard/
│   │   ├── dashboard.test.tsx
│   │   ├── dashboardData.ts
│   │   └── pages/
│   │       └── DashboardPage.tsx
│   └── website/
│       ├── pages/
│       │   └── WebsitePage.tsx
│       └── websiteData.ts
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── client.test.ts
│   │   ├── index.ts
│   │   └── types.ts
│   ├── auth/
│   │   ├── guard.tsx
│   │   └── token.ts
│   ├── i18n/
│   │   ├── dictionary.ts
│   │   ├── dictionary.test.ts
│   │   └── useLanguage.tsx
│   └── maps/
│       └── maplibre-config.ts
├── styles/
│   ├── dashboard.css
│   ├── global.css
│   ├── tokens.css
│   └── website.css
├── test/
│   └── setup.ts
└── main.tsx
```

### Điểm cần chỉnh

- `features/` đang đúng hướng nhưng tên chưa khớp mẫu anh muốn. Nên đổi thành `modules/`.
- `components/dashboard` là component riêng dashboard nhưng nằm ngoài feature/module.
- `components/shared` nên về `common/components`.
- `lib/api/types.ts` nên tách ra `interfaces/<domain>/`.
- `lib/i18n` nên về `config/i18n`.
- `lib/maps/maplibre-config.ts` nên về `config/maps` hoặc `config/map`.
- `styles/dashboard.css` và `styles/website.css` nên nằm trong module tương ứng.
- `styles/global.css`, `styles/tokens.css` có thể giữ global hoặc move vào `app/globals.css` nếu sau này theo Next.js.

---

## Cấu trúc target đề xuất cho repo hiện tại

Vì repo hiện đang là React/Vite-style, target nên nằm trong `frontend/src/` như sau:

```text
frontend/
├── Dockerfile
├── README.md
├── package.json
├── vite.config.ts
├── tsconfig.json
├── public/
│   ├── image/
│   └── ...
└── src/
    ├── app/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── provider.tsx
    │   ├── router.tsx
    │   ├── router.test.tsx
    │   └── globals.css
    ├── common/
    │   ├── apis/
    │   │   ├── client.ts
    │   │   ├── client.test.ts
    │   │   └── index.ts
    │   ├── components/
    │   │   ├── LanguageToggle.tsx
    │   │   └── ThemeToggle.tsx
    │   ├── constants/
    │   ├── helpers/
    │   ├── interfaces/
    │   └── types/
    ├── config/
    │   ├── _constant.ts
    │   ├── i18n/
    │   │   ├── dictionary.ts
    │   │   ├── dictionary.test.ts
    │   │   └── useLanguage.tsx
    │   ├── maps/
    │   │   └── maplibre-config.ts
    │   └── testing/
    │       └── setup.ts
    ├── interfaces/
    │   ├── alerts/
    │   ├── auth/
    │   ├── commands/
    │   ├── dashboard/
    │   ├── imagery/
    │   ├── prediction/
    │   ├── recommendation/
    │   ├── telemetry/
    │   ├── weather/
    │   └── zones/
    ├── lib/
    │   └── store/
    ├── modules/
    │   ├── admin/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   ├── hooks/
    │   │   ├── pages/
    │   │   │   └── AdminPage.tsx
    │   │   ├── styles/
    │   │   └── __tests__/
    │   │       └── AdminPage.test.tsx
    │   ├── auth/
    │   │   ├── components/
    │   │   ├── guard.tsx
    │   │   ├── token.ts
    │   │   └── __tests__/
    │   ├── dashboard/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   │   ├── DataFusionPanel.tsx
    │   │   │   ├── ImageryTimeline.tsx
    │   │   │   ├── ZoneImageryPanel.tsx
    │   │   │   ├── ZoneMap.tsx
    │   │   │   └── ZoneOverlay.tsx
    │   │   ├── data/
    │   │   │   └── dashboardData.ts
    │   │   ├── hooks/
    │   │   ├── pages/
    │   │   │   └── DashboardPage.tsx
    │   │   ├── styles/
    │   │   │   └── dashboard.css
    │   │   └── __tests__/
    │   │       └── dashboard.test.tsx
    │   ├── website/
    │   │   ├── components/
    │   │   ├── data/
    │   │   │   └── websiteData.ts
    │   │   ├── pages/
    │   │   │   └── WebsitePage.tsx
    │   │   ├── styles/
    │   │   │   └── website.css
    │   │   └── __tests__/
    │   ├── zones/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   └── hooks/
    │   ├── imagery/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   └── hooks/
    │   ├── telemetry/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   └── hooks/
    │   ├── alerts/
    │   │   ├── apis/
    │   │   ├── components/
    │   │   └── hooks/
    │   └── commands/
    │       ├── apis/
    │       ├── components/
    │       └── hooks/
    └── vite-env.d.ts
```

---

## Nếu sau này chuyển sang Next.js App Router

Nếu frontend chuyển sang Next.js như mẫu anh đưa, cấu trúc top-level có thể đổi thành:

```text
frontend/
├── app/
│   ├── (auth)/
│   ├── (main)/
│   ├── ThemeRegistry.tsx
│   ├── favicon.ico
│   ├── globals.css
│   ├── layout.tsx
│   ├── page.tsx
│   └── provider.tsx
├── common/
│   ├── apis/
│   ├── components/
│   ├── constants/
│   ├── helpers/
│   ├── interfaces/
│   └── types/
├── config/
│   ├── _constant.ts
│   ├── i18n/
│   ├── maps/
│   └── react-query/
├── interfaces/
│   ├── alerts/
│   ├── auth/
│   ├── commands/
│   ├── dashboard/
│   ├── imagery/
│   ├── prediction/
│   ├── recommendation/
│   ├── telemetry/
│   ├── weather/
│   └── zones/
├── lib/
│   └── redux/
├── modules/
│   ├── admin/
│   ├── auth/
│   ├── dashboard/
│   ├── website/
│   ├── zones/
│   ├── imagery/
│   ├── telemetry/
│   ├── alerts/
│   └── commands/
├── middleware.ts
├── public/
└── package.json
```

Lưu ý: hiện tại repo chưa phải Next.js, nên không nên tạo `app/layout.tsx`, `middleware.ts`, route group `(auth)` nếu chưa chuyển framework. Chỉ dùng tư duy tổ chức, không copy nguyên cây Next.js.

---

## Vai trò từng thư mục

### 1. `app/`

Chứa phần khởi động ứng dụng.

Nên có:

- `main.tsx`
- `App.tsx`
- `router.tsx`
- `provider.tsx`
- `globals.css`

Không nên có:

- component riêng dashboard/admin/website
- API theo domain
- business logic
- type domain lớn

### 2. `modules/`

Chứa từng chức năng/màn hình nghiệp vụ.

Ví dụ module hiện tại:

- `website`
- `dashboard`
- `admin`
- `auth`
- `zones`
- `imagery`
- `telemetry`
- `alerts`
- `commands`

Mỗi module có thể có:

```text
apis/
components/
hooks/
pages/
data/
styles/
__tests__/
```

Quy tắc:

- Component chỉ dùng trong dashboard thì ở `modules/dashboard/components`.
- CSS chỉ dùng trong website thì ở `modules/website/styles`.
- Mock/static data chỉ phục vụ dashboard thì ở `modules/dashboard/data`.
- Hook chỉ phục vụ imagery thì ở `modules/imagery/hooks`.

### 3. `common/`

Chứa code dùng chung thật sự.

Nên có:

- `common/apis/client.ts`: HTTP client base.
- `common/components`: component dùng nhiều module.
- `common/constants`: constant chung.
- `common/helpers`: helper pure/generic.
- `common/interfaces`: interface dùng chung nhiều domain.
- `common/types`: type generic.

Không đưa code vào `common` chỉ vì “có thể sau này dùng”. Chỉ đưa vào khi có ít nhất 2 module dùng thật.

### 4. `config/`

Chứa cấu hình app.

Nên có:

- `_constant.ts`
- `i18n/`
- `maps/`
- `react-query/` nếu sau này dùng TanStack Query
- `testing/` cho test setup

### 5. `interfaces/`

Chứa interface/type theo domain nghiệp vụ.

Ví dụ:

```text
interfaces/zones/
interfaces/imagery/
interfaces/telemetry/
interfaces/prediction/
interfaces/recommendation/
interfaces/alerts/
interfaces/commands/
```

Quy tắc:

- Type contract từ backend domain nào thì đặt vào domain đó.
- Không gom tất cả vào một file `types.ts`.
- Type dùng chung nhiều domain thì đưa vào `common/types` hoặc `common/interfaces`.

### 6. `lib/`

Chỉ chứa tooling cấp thấp hoặc state infrastructure.

Ví dụ:

- `lib/store/`
- `lib/redux/` nếu dùng Redux
- helper adapter cho thư viện bên thứ ba nếu không thuộc domain nào

Không dùng `lib/` làm nơi gom code chưa biết để đâu.

---

## Mapping từ cấu trúc hiện tại sang cấu trúc mới

### App shell

```text
frontend/src/main.tsx
  -> frontend/src/app/main.tsx

frontend/src/app/providers.tsx
  -> frontend/src/app/provider.tsx

frontend/src/app/router.tsx
  -> frontend/src/app/router.tsx

frontend/src/app/router.test.tsx
  -> frontend/src/app/router.test.tsx

frontend/src/styles/global.css
  -> frontend/src/app/globals.css

frontend/src/styles/tokens.css
  -> frontend/src/common/constants/tokens.css hoặc giữ import trong app/globals.css
```

Có thể giữ `frontend/src/main.tsx` làm shim tạm nếu Vite đang trỏ vào file này.

### Common

```text
frontend/src/components/shared/LanguageToggle.tsx
  -> frontend/src/common/components/LanguageToggle.tsx

frontend/src/components/shared/ThemeToggle.tsx
  -> frontend/src/common/components/ThemeToggle.tsx

frontend/src/lib/api/client.ts
  -> frontend/src/common/apis/client.ts

frontend/src/lib/api/client.test.ts
  -> frontend/src/common/apis/client.test.ts

frontend/src/lib/api/index.ts
  -> frontend/src/common/apis/index.ts
```

### Config

```text
frontend/src/lib/i18n/dictionary.ts
  -> frontend/src/config/i18n/dictionary.ts

frontend/src/lib/i18n/dictionary.test.ts
  -> frontend/src/config/i18n/dictionary.test.ts

frontend/src/lib/i18n/useLanguage.tsx
  -> frontend/src/config/i18n/useLanguage.tsx

frontend/src/lib/maps/maplibre-config.ts
  -> frontend/src/config/maps/maplibre-config.ts

frontend/src/test/setup.ts
  -> frontend/src/config/testing/setup.ts
```

### Modules

```text
frontend/src/features/admin/pages/AdminPage.tsx
  -> frontend/src/modules/admin/pages/AdminPage.tsx

frontend/src/features/admin/pages/AdminPage.test.tsx
  -> frontend/src/modules/admin/__tests__/AdminPage.test.tsx

frontend/src/features/dashboard/pages/DashboardPage.tsx
  -> frontend/src/modules/dashboard/pages/DashboardPage.tsx

frontend/src/features/dashboard/dashboardData.ts
  -> frontend/src/modules/dashboard/data/dashboardData.ts

frontend/src/features/dashboard/dashboard.test.tsx
  -> frontend/src/modules/dashboard/__tests__/dashboard.test.tsx

frontend/src/components/dashboard/DataFusionPanel.tsx
  -> frontend/src/modules/dashboard/components/DataFusionPanel.tsx

frontend/src/components/dashboard/ImageryTimeline.tsx
  -> frontend/src/modules/dashboard/components/ImageryTimeline.tsx

frontend/src/components/dashboard/ZoneImageryPanel.tsx
  -> frontend/src/modules/dashboard/components/ZoneImageryPanel.tsx

frontend/src/components/dashboard/ZoneMap.tsx
  -> frontend/src/modules/dashboard/components/ZoneMap.tsx

frontend/src/components/dashboard/ZoneOverlay.tsx
  -> frontend/src/modules/dashboard/components/ZoneOverlay.tsx

frontend/src/styles/dashboard.css
  -> frontend/src/modules/dashboard/styles/dashboard.css

frontend/src/features/website/pages/WebsitePage.tsx
  -> frontend/src/modules/website/pages/WebsitePage.tsx

frontend/src/features/website/websiteData.ts
  -> frontend/src/modules/website/data/websiteData.ts

frontend/src/styles/website.css
  -> frontend/src/modules/website/styles/website.css

frontend/src/lib/auth/guard.tsx
  -> frontend/src/modules/auth/guard.tsx

frontend/src/lib/auth/token.ts
  -> frontend/src/modules/auth/token.ts
```

### Interfaces

```text
frontend/src/lib/api/types.ts
  -> split into frontend/src/interfaces/*
```

Tách gợi ý:

```text
interfaces/zones/
interfaces/imagery/
interfaces/telemetry/
interfaces/prediction/
interfaces/recommendation/
interfaces/alerts/
interfaces/commands/
interfaces/auth/
```

---

## Kế hoạch triển khai theo phase

### Phase FE 0 — Chốt baseline

Mục tiêu: biết trạng thái hiện tại trước khi đổi cấu trúc.

Việc cần làm:

1. Chạy test frontend.
2. Chạy build/typecheck.
3. Ghi nhận lỗi hiện tại nếu có.

Lệnh gợi ý:

```bash
npm test
npm run build
```

Nếu script khác, kiểm tra `frontend/package.json` trước.

---

### Phase FE 1 — Tạo khung thư mục mới

Tạo các thư mục:

```text
src/common/apis/
src/common/components/
src/common/constants/
src/common/helpers/
src/common/interfaces/
src/common/types/
src/config/i18n/
src/config/maps/
src/config/testing/
src/interfaces/
src/lib/store/
src/modules/
```

Chưa xóa thư mục cũ.

---

### Phase FE 2 — Move common và config trước

Move nhóm ít rủi ro:

```text
components/shared/* -> common/components/*
lib/api/client.ts   -> common/apis/client.ts
lib/api/index.ts    -> common/apis/index.ts
lib/i18n/*          -> config/i18n/*
lib/maps/*          -> config/maps/*
test/setup.ts       -> config/testing/setup.ts
```

Sau đó update imports và test setup config.

---

### Phase FE 3 — Đổi `features/` thành `modules/`

Move từng module một:

```text
features/admin     -> modules/admin
features/dashboard -> modules/dashboard
features/website   -> modules/website
```

Không đổi logic trong cùng phase này. Chỉ đổi vị trí và import.

---

### Phase FE 4 — Colocate component/style/data vào module

Dashboard:

```text
components/dashboard/* -> modules/dashboard/components/*
styles/dashboard.css   -> modules/dashboard/styles/dashboard.css
```

Website:

```text
styles/website.css -> modules/website/styles/website.css
```

Data:

```text
modules/dashboard/dashboardData.ts -> modules/dashboard/data/dashboardData.ts
modules/website/websiteData.ts     -> modules/website/data/websiteData.ts
```

Tests:

```text
modules/dashboard/dashboard.test.tsx -> modules/dashboard/__tests__/dashboard.test.tsx
modules/admin/pages/AdminPage.test.tsx -> modules/admin/__tests__/AdminPage.test.tsx
```

---

### Phase FE 5 — Move auth thành module riêng

```text
lib/auth/guard.tsx -> modules/auth/guard.tsx
lib/auth/token.ts  -> modules/auth/token.ts
```

Nếu router đang dùng auth guard, update import sang `modules/auth`.

---

### Phase FE 6 — Split API interfaces theo domain

Tách `lib/api/types.ts` thành nhiều domain trong `interfaces/`:

```text
interfaces/zones/index.ts
interfaces/imagery/index.ts
interfaces/telemetry/index.ts
interfaces/prediction/index.ts
interfaces/recommendation/index.ts
interfaces/alerts/index.ts
interfaces/commands/index.ts
interfaces/auth/index.ts
```

Sau đó update import trong:

- common API client
- dashboard module
- admin module
- imagery components
- zone map/status components

---

### Phase FE 7 — Chuẩn hóa apis theo module

Giữ HTTP base client ở:

```text
common/apis/client.ts
```

Domain API function đặt trong module hoặc common tùy phạm vi:

```text
modules/dashboard/apis/dashboardApi.ts
modules/admin/apis/adminApi.ts
modules/zones/apis/zonesApi.ts
modules/imagery/apis/imageryApi.ts
modules/telemetry/apis/telemetryApi.ts
```

Quy tắc:

- API chỉ phục vụ 1 module thì để trong module đó.
- API dùng nhiều module thì cân nhắc `common/apis`.
- Type response/request vẫn ở `interfaces/<domain>`.

---

### Phase FE 8 — Dọn thư mục cũ

Chỉ xóa khi test/build pass:

```text
src/components/dashboard/
src/components/shared/
src/features/
src/lib/api/types.ts
src/lib/auth/
src/lib/i18n/
src/lib/maps/
src/test/
src/styles/dashboard.css
src/styles/website.css
```

Có thể giữ:

```text
src/styles/
```

nếu còn global token/base style. Nếu không, chuyển hết về:

```text
src/app/globals.css
src/common/constants/tokens.css
```

---

## Quy ước đặt tên module

Module dùng kebab-case nếu tên nhiều từ:

```text
modules/zone-map/
modules/imagery-timeline/
modules/admin-dashboard/
```

Nhưng với repo hiện tại nên giữ đơn giản:

```text
modules/admin/
modules/auth/
modules/dashboard/
modules/website/
modules/zones/
modules/imagery/
modules/telemetry/
modules/alerts/
modules/commands/
```

File React component dùng PascalCase:

```text
DashboardPage.tsx
ZoneMap.tsx
ThemeToggle.tsx
```

Hook dùng `use` prefix:

```text
useZoneStatus.ts
useImageryTimeline.ts
```

API file dùng camelCase:

```text
dashboardApi.ts
zonesApi.ts
imageryApi.ts
```

---

## Import convention sau refactor

Nếu đang dùng alias `@/`, import nên như sau:

```ts
import { apiClient } from '@/common/apis'
import { ThemeToggle } from '@/common/components/ThemeToggle'
import { DashboardPage } from '@/modules/dashboard/pages/DashboardPage'
import type { ZoneStatusResponse } from '@/interfaces/zones'
```

Không nên import xuyên sâu vào nội bộ module khác, ví dụ tránh:

```ts
import { Something } from '@/modules/dashboard/components/internal/Something'
```

Nếu module khác cần dùng, promote component đó lên `common/components` hoặc tạo public export rõ ràng.

---

## Rủi ro cần kiểm soát

### 1. Move CSS nhưng UI vẫn build pass

CSS mất import có thể không làm test fail.

Cần kiểm tra bằng browser sau các phase liên quan style:

- website page
- dashboard page
- admin page
- responsive 320, 768, 1024, 1440
- theme toggle
- language toggle

### 2. Test setup path

Move `src/test/setup.ts` sang `src/config/testing/setup.ts` phải update Vitest config.

### 3. Alias path

Nếu `tsconfig` hoặc Vite alias đang trỏ `src`, vẫn ổn. Nếu có hardcoded path cũ, phải update.

### 4. Split interfaces bị duplicate

Không copy cùng một type vào nhiều domain.

Nếu type dùng chung, đưa vào:

```text
common/types/
common/interfaces/
```

### 5. Common bị phình to

`common/` chỉ dành cho code dùng chung thật sự. Không biến `common` thành thư mục rác mới.

---

## Thứ tự PR frontend gợi ý

1. `refactor: add frontend module-based folders`
2. `refactor: move common components and config`
3. `refactor: rename frontend features to modules`
4. `refactor: colocate dashboard components and styles`
5. `refactor: colocate website assets`
6. `refactor: move auth into module boundary`
7. `refactor: split frontend interfaces by domain`
8. `test: update frontend imports and setup paths`
9. `chore: remove legacy frontend folders`

---

## Khuyến nghị triển khai

Không copy nguyên cây Next.js mẫu vào repo hiện tại nếu chưa chuyển framework.

Nên lấy tư duy tổ chức:

- `app` cho app shell
- `modules` cho chức năng
- `common` cho dùng chung
- `config` cho cấu hình
- `interfaces` cho contract/type theo domain
- `lib` cho state/tooling cấp thấp

Triển khai từng phase nhỏ. Sau mỗi phase chạy:

```bash
npm test
npm run build
```

Với phase có UI/CSS, phải mở browser kiểm tra trực tiếp.

---

## Kết luận frontend

Cấu trúc FE nên điều chỉnh theo hướng giống mẫu anh đưa nhưng phù hợp repo hiện tại:

```text
src/app
src/common
src/config
src/interfaces
src/lib
src/modules
```

`modules/` là trung tâm của code nghiệp vụ. `common/` và `config/` chỉ phục vụ nền tảng dùng chung. Cách này giúp frontend đồng bộ tư duy với backend: chia theo chức năng, giảm thư mục kiểu gom chung như `components`, `lib`, `styles` bị phình to theo thời gian.