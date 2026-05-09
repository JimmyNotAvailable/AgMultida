# Hướng Dẫn Xây Dựng Container Docker

Tài liệu này mô tả cách build và chạy các container trong repo `AgMultida`, chia theo 4 nhóm chính:

1. Front-end
2. Backend
3. Database
4. Module ML + AI

Mục tiêu: giúp team hiểu rõ mỗi nhóm container gồm gì, build từ đâu, phụ thuộc gì, và cách chạy riêng lẻ hoặc chạy toàn bộ bằng `docker-compose`.

---

## 1. Tổng quan kiến trúc container

Theo `docker-compose.yml`, hệ thống hiện tại gồm các service chính sau:

### 1.1. Nhóm Front-end
- `frontend`

### 1.2. Nhóm Backend
- `api-gateway`
- `ingestion-service`
- `decision-engine`

### 1.3. Nhóm Database / hạ tầng dữ liệu
- `postgres`
- `redis`
- `minio`
- `minio-init`
- `mosquitto`
- `db-migrate`
- `db-seed`

> Lưu ý: về mặt thuần kỹ thuật, `redis`, `minio`, `mosquitto` là hạ tầng phụ trợ chứ không phải database quan hệ. Tuy nhiên theo cách gom nhóm triển khai, chúng thuộc nhóm Database / data infrastructure vì phục vụ lưu trữ, cache, object storage và messaging cho backend + ML/AI.

### 1.4. Nhóm Module ML + AI
- `ai-serving`
- `model-exporter`
- `data-collector`

---

## 2. File Docker hiện có trong repo

Các Dockerfile đang có:

- `frontend/Dockerfile`
- `backend/api_gateway/Dockerfile`
- `backend/ai_serving/Dockerfile`
- `backend/decision_engine/Dockerfile`
- `backend/ingestion_service/Dockerfile`

File orchestration chính:

- `docker-compose.yml`

---

## 3. Chuẩn bị trước khi build

## 3.1. Yêu cầu cài đặt

Máy local hoặc server cần có:

- Docker
- Docker Compose plugin (`docker compose`)

Kiểm tra nhanh:

```bash
docker --version
docker compose version
```

## 3.2. Chuẩn bị biến môi trường

Project dùng file `.env` để nạp cấu hình cho container.

Bắt đầu từ file mẫu:

```bash
cp .env.example .env
```

Trên Windows PowerShell có thể dùng:

```powershell
Copy-Item .env.example .env
```

Các biến quan trọng cần điền thật trước khi chạy:

- `POSTGRES_PASSWORD`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `JWT_SECRET`
- `API_KEY_HASH_SALT`

Các biến port và URL mặc định hiện có:

- `FRONTEND_PORT=8080`
- `API_GATEWAY_PORT=8000`
- `AI_SERVING_PORT=8001`
- `DECISION_ENGINE_PORT=8002`
- `INGESTION_SERVICE_PORT=8003`
- `POSTGRES_PORT=5432`
- `REDIS_PORT=6379`
- `MINIO_PORT=9000`
- `MINIO_CONSOLE_PORT=9001`
- `MQTT_PORT=1883`

---

## 4. Build và chạy toàn bộ hệ thống

Đây là cách chuẩn cho môi trường local dev hoặc demo kỹ thuật.

## 4.1. Build toàn bộ image

```bash
docker compose build
```

## 4.2. Chạy toàn bộ stack

```bash
docker compose up -d
```

## 4.3. Kiểm tra trạng thái

```bash
docker compose ps
```

## 4.4. Xem log

```bash
docker compose logs -f
```

Hoặc xem log từng service:

```bash
docker compose logs -f frontend
docker compose logs -f api-gateway
docker compose logs -f ai-serving
```

## 4.5. Dừng hệ thống

```bash
docker compose down
```

Nếu muốn xóa luôn volume dữ liệu:

```bash
docker compose down -v
```

**Cảnh báo:** lệnh `docker compose down -v` sẽ xóa dữ liệu trong các volume như `pg_data`, `minio_data`. Chỉ dùng khi chắc chắn không cần giữ dữ liệu cũ.

---

## 5. Hướng dẫn theo từng nhóm container

# 5.1. Front-end container

## Thành phần
- `frontend`

## Vai trò
Container này build giao diện web từ thư mục `frontend/` và phục vụ bản build tĩnh qua Nginx.

## Dockerfile sử dụng
- `frontend/Dockerfile`

## Cách Dockerfile hoạt động

`frontend/Dockerfile` dùng chiến lược multi-stage:

### Stage 1: `deps`
- Base image: `node:20-alpine`
- Copy:
  - `frontend/package.json`
  - `frontend/package-lock.json`
- Cài dependency bằng:

```bash
npm ci
```

### Stage 2: `build`
- Copy `node_modules` từ stage trước
- Copy toàn bộ mã nguồn `frontend/`
- Nhận build args:
  - `VITE_API_BASE_URL`
  - `VITE_WS_URL`
- Chạy:

```bash
npm run build
```

### Stage 3: runtime
- Base image: `nginx:1.27-alpine`
- Copy thư mục `dist` sang:
  - `/usr/share/nginx/html`
- Expose port `80`

## Build riêng container Front-end

```bash
docker build -t agmultida-frontend -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  --build-arg VITE_WS_URL=ws://localhost:8000/ws/updates \
  .
```

PowerShell:

```powershell
docker build -t agmultida-frontend -f frontend/Dockerfile `
  --build-arg VITE_API_BASE_URL=http://localhost:8000 `
  --build-arg VITE_WS_URL=ws://localhost:8000/ws/updates `
  .
```

## Chạy riêng container Front-end

```bash
docker run -d --name agmultida-frontend -p 8080:80 agmultida-frontend
```

## Lưu ý quan trọng
- `VITE_API_BASE_URL` và `VITE_WS_URL` được nhúng ở thời điểm build FE.
- Nếu đổi host API hoặc WebSocket, cần build lại image FE.
- Trong `docker-compose.yml`, FE đang map:
  - `${FRONTEND_PORT:-8080}:80`

---

# 5.2. Backend containers

## Thành phần
- `api-gateway`
- `ingestion-service`
- `decision-engine`

## Vai trò từng service

### `api-gateway`
- Cổng vào chính của hệ thống backend
- Expose ra host qua port `8000`
- Gọi nội bộ sang:
  - `ai-serving`
  - `ingestion-service`
  - `decision-engine`
- Có healthcheck tới:
  - `http://localhost:8000/v1/healthz`

### `ingestion-service`
- Phụ trách ingestion / tiếp nhận dữ liệu
- Dùng `postgres` và `redis`
- Expose port `8003`
- Healthcheck:
  - `http://localhost:8003/healthz`

### `decision-engine`
- Phụ trách logic ra quyết định
- Dùng `redis`
- Expose port `8002`
- Healthcheck:
  - `http://localhost:8002/healthz`

## Dockerfile sử dụng

### `backend/api_gateway/Dockerfile`
Dùng cho:
- `api-gateway`
- `db-migrate`
- `db-seed`
- `data-collector`

Cấu trúc:
- Base image: `python:3.12-slim`
- Thiết lập:
  - `PYTHONDONTWRITEBYTECODE=1`
  - `PYTHONUNBUFFERED=1`
  - `PYTHONPATH=/app/backend`
- Copy vào image:
  - `requirements.txt`
  - `backend/`
  - `ai_system/`
  - `metadata/`
  - `contracts/`
  - `artifacts/`
  - `data/`
- Cài package bằng:

```bash
pip install --no-cache-dir -r /app/requirements.txt
```

### `backend/ingestion_service/Dockerfile`
- Base image: `python:3.12-slim`
- Copy:
  - `requirements.txt`
  - `backend/`
  - `metadata/`
- `WORKDIR /app/backend`

### `backend/decision_engine/Dockerfile`
- Base image: `python:3.12-slim`
- Copy:
  - `requirements.txt`
  - `backend/`
  - `contracts/`
- `WORKDIR /app/backend`

## Build riêng từng container Backend

### API Gateway

```bash
docker build -t agmultida-api-gateway -f backend/api_gateway/Dockerfile .
```

### Ingestion Service

```bash
docker build -t agmultida-ingestion-service -f backend/ingestion_service/Dockerfile .
```

### Decision Engine

```bash
docker build -t agmultida-decision-engine -f backend/decision_engine/Dockerfile .
```

## Chạy backend bằng compose

Khuyến nghị dùng `docker compose` thay vì `docker run` riêng lẻ vì backend có phụ thuộc chéo với DB, Redis, MinIO và service ML/AI.

Chạy nhóm backend + hạ tầng liên quan:

```bash
docker compose up -d postgres redis minio mosquitto ai-serving decision-engine ingestion-service api-gateway
```

## Biến môi trường nội bộ đáng chú ý

### `api-gateway`
- `DATABASE_URL`
- `REDIS_URL`
- `AI_SERVING_URL=http://ai-serving:8001`
- `INGESTION_SERVICE_URL=http://ingestion-service:8003`

### `ingestion-service`
- `DATABASE_URL`
- `REDIS_URL=redis://redis:6379/0`

### `decision-engine`
- nhận biến từ `.env`

## Kiểm tra nhanh sau khi chạy

```bash
curl http://localhost:8000/v1/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz
```

---

# 5.3. Database và data infrastructure containers

## Thành phần
- `postgres`
- `redis`
- `minio`
- `minio-init`
- `mosquitto`
- `db-migrate`
- `db-seed`

## Vai trò từng service

### `postgres`
- CSDL chính
- Image:
  - `timescale/timescaledb:latest-pg15`
- Volume:
  - `pg_data:/var/lib/postgresql/data`
- Port host:
  - `${POSTGRES_PORT:-5432}:5432`

### `redis`
- Cache / state tạm / rate limiting support
- Image:
  - `redis:7-alpine`
- Port host:
  - `${REDIS_PORT:-6379}:6379`

### `minio`
- Object storage cho model artifacts, raw images, exports
- Image:
  - `minio/minio`
- Port host:
  - `${MINIO_PORT:-9000}:9000`
  - `${MINIO_CONSOLE_PORT:-9001}:9001`
- Volume:
  - `minio_data:/data`

### `minio-init`
- Container khởi tạo bucket trên MinIO
- Chỉ chạy khi dùng profile `init`
- Tạo các bucket:
  - `models`
  - `raw-images`
  - `aligned-features`
  - `exports`

### `mosquitto`
- MQTT broker
- Image:
  - `eclipse-mosquitto:2`
- Port host:
  - `${MQTT_PORT:-1883}:1883`

### `db-migrate`
- Chạy migration DB bằng Alembic
- Dùng Dockerfile của `backend/api_gateway`
- Command:

```bash
alembic upgrade head
```

### `db-seed`
- Seed dữ liệu ban đầu
- Dùng Dockerfile của `backend/api_gateway`
- Command:

```bash
python scripts/seed_zones.py
```

## Build nhóm Database

`postgres`, `redis`, `minio`, `minio-init`, `mosquitto` dùng image có sẵn, không cần build local.

Chỉ các service sau cần build vì chạy code trong repo:
- `db-migrate`
- `db-seed`

Build:

```bash
docker compose build db-migrate db-seed
```

## Chạy hạ tầng database trước

```bash
docker compose up -d postgres redis minio mosquitto
```

## Chạy khởi tạo bucket + migration + seed

```bash
docker compose --profile init up minio-init db-migrate db-seed
```

> Có thể cần chạy `postgres`, `minio` ổn định trước rồi mới chạy profile `init`.

## Kiểm tra nhanh

### Postgres

```bash
docker compose ps postgres
```

### Redis

```bash
docker compose ps redis
```

### MinIO console
Mở trình duyệt:

- `http://localhost:9001`

### MQTT
Kiểm tra service sống:

```bash
docker compose ps mosquitto
```

---

# 5.4. Module container ML + AI

## Thành phần
- `ai-serving`
- `model-exporter`
- `data-collector`

## Vai trò từng service

### `ai-serving`
- Service inference / serving model AI
- Expose port `8001`
- Dùng MinIO như nguồn object storage
- Command runtime:

```bash
uvicorn ai_serving.main:app --host 0.0.0.0 --port 8001
```

### `model-exporter`
- Chạy export model ONNX
- Thuộc profile `ml`
- Command:

```bash
python ml_pipeline/export/export_onnx.py --dry-run
```

### `data-collector`
- Chạy data collection dry-run
- Thuộc profile `data`
- Command:

```bash
python scripts/run_data_collection.py --dry-run
```

## Dockerfile sử dụng

### `backend/ai_serving/Dockerfile`
Dùng cho:
- `ai-serving`
- `model-exporter`

Cấu trúc:
- Base image: `python:3.12-slim`
- Copy:
  - `requirements.txt`
  - `backend/`
  - `ai_system/`
  - `metadata/`
  - `contracts/`
- `WORKDIR /app/backend`

## Build riêng nhóm ML + AI

### AI Serving

```bash
docker build -t agmultida-ai-serving -f backend/ai_serving/Dockerfile .
```

### Model Exporter
`model-exporter` dùng chung Dockerfile với `ai-serving`, nên không cần Dockerfile riêng.

### Data Collector
`data-collector` đang dùng lại `backend/api_gateway/Dockerfile`.

## Chạy nhóm ML + AI bằng compose

### Chạy AI Serving

```bash
docker compose up -d minio ai-serving
```

### Chạy exporter profile ML

```bash
docker compose --profile ml up model-exporter
```

### Chạy collector profile Data

```bash
docker compose --profile data up data-collector
```

## Volume mount liên quan

### `model-exporter`
- `./artifacts:/app/artifacts`

### `data-collector`
- `./data:/app/data`
- `./reports:/app/reports`

## Kiểm tra health

```bash
curl http://localhost:8001/healthz
```

---

## 6. Thứ tự khởi động khuyến nghị

Để giảm lỗi phụ thuộc, nên khởi động theo thứ tự:

1. Database và hạ tầng dữ liệu
   - `postgres`
   - `redis`
   - `minio`
   - `mosquitto`
2. Khởi tạo dữ liệu
   - `minio-init`
   - `db-migrate`
   - `db-seed`
3. Module ML + AI
   - `ai-serving`
4. Backend services
   - `decision-engine`
   - `ingestion-service`
   - `api-gateway`
5. Front-end
   - `frontend`

Nếu dùng compose full-stack thì dependency và healthcheck đã hỗ trợ phần lớn thứ tự này.

---

## 7. Các lệnh thao tác nhanh theo nhóm

## 7.1. Build toàn bộ

```bash
docker compose build
```

## 7.2. Chạy full stack

```bash
docker compose up -d
```

## 7.3. Chạy riêng Front-end

```bash
docker compose up -d frontend
```

## 7.4. Chạy riêng Backend core

```bash
docker compose up -d api-gateway ingestion-service decision-engine
```

## 7.5. Chạy riêng Database core

```bash
docker compose up -d postgres redis minio mosquitto
```

## 7.6. Chạy profile init

```bash
docker compose --profile init up minio-init db-migrate db-seed
```

## 7.7. Chạy profile ML

```bash
docker compose --profile ml up model-exporter
```

## 7.8. Chạy profile Data

```bash
docker compose --profile data up data-collector
```

---

## 8. Một số lỗi thường gặp

## 8.1. FE gọi sai API host

Nguyên nhân:
- build FE với `VITE_API_BASE_URL` sai
- đổi host nhưng không build lại image

Cách xử lý:
- build lại `frontend` với đúng `--build-arg`
- hoặc chỉnh `.env` rồi chạy lại:

```bash
docker compose build frontend
docker compose up -d frontend
```

## 8.2. Backend không kết nối được Postgres

Nguyên nhân thường gặp:
- chưa set `POSTGRES_PASSWORD`
- dùng nhầm `DATABASE_URL` host machine thay vì `DATABASE_URL_DOCKER`
- `postgres` chưa healthy

Cách xử lý:
- kiểm tra `.env`
- kiểm tra `docker compose ps`
- xem log:

```bash
docker compose logs -f postgres
docker compose logs -f api-gateway
```

## 8.3. MinIO chạy nhưng chưa có bucket

Nguyên nhân:
- chưa chạy profile `init`
- `minio-init` chưa chạy thành công

Cách xử lý:

```bash
docker compose --profile init up minio-init
```

## 8.4. AI Serving không healthy

Nguyên nhân:
- model artifact / config chưa sẵn
- MinIO chưa sẵn sàng
- dependency Python cài lỗi khi build

Cách xử lý:

```bash
docker compose logs -f ai-serving
docker compose build ai-serving
```

---

## 9. Khuyến nghị vận hành

- Dùng `.env` riêng cho từng môi trường: local dev, staging, production.
- Không commit secret thật vào git.
- Với Front-end, nhớ rằng URL API và WebSocket được đóng gói tại build time.
- Với Backend và ML/AI, ưu tiên chạy qua `docker compose` để service discovery nội bộ dùng đúng hostname như:
  - `postgres`
  - `redis`
  - `minio`
  - `ai-serving`
  - `ingestion-service`
- Khi cần reset sạch môi trường local, cân nhắc:

```bash
docker compose down -v
```

nhưng chỉ dùng khi chấp nhận mất dữ liệu local.

---

## 10. Kết luận

Hiện tại repo đã có nền Docker tương đối rõ theo 4 cụm:

- **Front-end**: 1 container phục vụ giao diện web bằng Nginx
- **Backend**: nhóm FastAPI/service nghiệp vụ chính
- **Database**: Postgres + Redis + MinIO + MQTT + init/migration/seed
- **ML + AI**: AI serving, model exporter, data collector

Nếu cần triển khai local nhanh, cách phù hợp nhất là:

```bash
docker compose build
docker compose up -d
```

Nếu cần chạy theo từng lớp, nên đi theo thứ tự:

- Database
- Init dữ liệu
- ML + AI
- Backend
- Front-end
