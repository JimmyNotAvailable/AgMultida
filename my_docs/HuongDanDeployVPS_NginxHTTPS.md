# Hướng Dẫn Deploy AgMultida Lên VPS Với Docker Compose + Nginx HTTPS

## 1. Mục tiêu

Mục tiêu deploy VPS:

- chạy toàn bộ stack bằng Docker Compose
- dùng Nginx edge proxy cho HTTPS
- chỉ public `80` và `443`
- giữ Postgres, Redis, MinIO, Mosquitto, FastAPI services trong Docker network nội bộ
- operator chỉ cần chuẩn bị `.env.production`, sau đó chạy một script deploy
- hỗ trợ 2 mode TLS: `self-signed` cho IP-only và `letsencrypt` cho domain thật

Trạng thái phù hợp: **staging / internal QA / pilot có kiểm soát**.

---

## 2. Kiến trúc

```text
Internet
  |
  v
Nginx edge :80/:443
  |
  +--> frontend:80
  |
  +--> api-gateway:8000
            |
            +--> ai-serving:8001
            +--> ingestion-service:8003
            +--> decision-engine:8002
            +--> postgres:5432
            +--> redis:6379
            +--> minio:9000
            +--> mosquitto:1883
```

Route public:

| Public path | Upstream nội bộ |
| --- | --- |
| `/` | `frontend:80` |
| `/v1/` | `api-gateway:8000` |
| `/ws/` | `api-gateway:8000` |
| `/.well-known/acme-challenge/` | `/var/www/certbot` |
| `/healthz` | handled by Nginx |

Frontend container có SPA fallback, nên refresh trực tiếp `/dashboard` và `/admin` không bị 404.

---

## 3. File triển khai

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `nginx/nginx.conf`
- `frontend/nginx.conf`
- `frontend/Dockerfile`
- `deploy/vps/deploy_vps.sh`
- `deploy/vps/renew_cert.sh`
- `my_docs/ChecklistLenhDeployUbuntuVPS.md`

`docker-compose.prod.yml` là override cho VPS, dùng cùng `docker-compose.yml`.

---

## 4. Chuẩn bị VPS Ubuntu

### 4.1. Cài Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git ufw
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Đăng xuất rồi đăng nhập lại.

### 4.2. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Không mở `5432`, `6379`, `8000`, `8001`, `8002`, `8003`, `9000`, `9001`, `1883`.

---

## 5. Chuẩn bị source và env

```bash
sudo mkdir -p /opt/agmultida
sudo chown -R $USER:$USER /opt/agmultida
git clone <REPO_URL> /opt/agmultida/app
cd /opt/agmultida/app
cp .env.example .env.production
chmod 600 .env.production
```

### 5.1. Mẫu IP-only, self-signed

```text
POSTGRES_PASSWORD=<strong-password>
DATABASE_URL=postgresql://agtech:<strong-password>@localhost:5432/agtech
DATABASE_URL_DOCKER=postgresql://agtech:<strong-password>@postgres:5432/agtech
MINIO_ACCESS_KEY=<strong-access-key>
MINIO_SECRET_KEY=<strong-secret-key>
JWT_SECRET=<random-256-bit-secret>
API_KEY_HASH_SALT=<random-salt>
INTERNAL_API_KEY=<random-internal-key-16+-chars>
INTERNAL_API_KEY_HEADER=X-Internal-API-Key
APP_ENV=production
LOG_LEVEL=INFO
AUTH_REQUIRED=true
WS_REQUIRE_AUTH=true
ENABLE_HSTS=true
TRUSTED_HOSTS=159.223.92.233,localhost,127.0.0.1,api-gateway
CORS_ORIGINS=https://159.223.92.233
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_REDIS_URL=redis://redis:6379/0
REDIS_URL=redis://redis:6379/0
VITE_API_BASE_URL=/v1
VITE_WS_URL=/ws/updates
DOMAIN=159.223.92.233
TLS_CERT_MODE=self-signed
CERTBOT_EMAIL=
SELF_SIGNED_CERT_DAYS=365
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

### 5.2. Mẫu domain thật, Let's Encrypt

```text
CORS_ORIGINS=https://<your-domain>
TRUSTED_HOSTS=<your-domain>,localhost,127.0.0.1,api-gateway
VITE_API_BASE_URL=/v1
VITE_WS_URL=/ws/updates
DOMAIN=<your-domain>
TLS_CERT_MODE=letsencrypt
CERTBOT_EMAIL=admin@<your-domain>
SELF_SIGNED_CERT_DAYS=365
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

Các biến nội bộ quan trọng:

- `API_KEY_HASH_SALT`: salt để hash API key nội bộ
- `INTERNAL_API_KEY`: key gateway dùng gọi internal services
- `INTERNAL_API_KEY_HEADER`: header nội bộ, mặc định `X-Internal-API-Key`
- `DATABASE_URL_DOCKER`: DSN dùng trong Docker network cho `db-migrate`, `db-seed`, backend services
- `RATE_LIMIT_BACKEND=redis`: nên dùng trên VPS thay vì memory

`deploy/vps/deploy_vps.sh` đang chặn placeholder cho các biến bắt buộc. Không để các giá trị như `CHANGE_ME_*`, `your_*`, `test`, `test-*`.

---

## 6. Cách deploy hiện tại

### 6.1. IP-only, không có domain thật

Đặt `.env.production` với:

```text
DOMAIN=159.223.92.233
TLS_CERT_MODE=self-signed
VITE_API_BASE_URL=/v1
VITE_WS_URL=/ws/updates
```

Rồi chạy:

```bash
bash deploy/vps/deploy_vps.sh
```

Script sẽ tự tạo self-signed certificate cho IP nếu chưa có.

### 6.2. Có domain thật

Đặt `.env.production` với:

```text
DOMAIN=<your-domain>
TLS_CERT_MODE=letsencrypt
CERTBOT_EMAIL=admin@<your-domain>
VITE_API_BASE_URL=/v1
VITE_WS_URL=/ws/updates
```

Trỏ DNS `A` record về IP VPS trước khi chạy. Sau đó:

```bash
bash deploy/vps/deploy_vps.sh
```

Script sẽ xin cert đầu tiên bằng `certbot certonly --standalone -d $DOMAIN`.

---

## 7. Script deploy đang làm gì

`deploy/vps/deploy_vps.sh` hiện tại sẽ tự:

1. kiểm tra `docker`, `python3`, `.env.production`, `docker-compose.yml`, `docker-compose.prod.yml`, `nginx/nginx.conf`
2. đọc các biến bắt buộc như `DOMAIN`, `POSTGRES_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `JWT_SECRET`, `API_KEY_HASH_SALT`, `VITE_API_BASE_URL`, `VITE_WS_URL`
3. ép mode `self-signed` nếu `DOMAIN` là IPv4
4. tạo cert thư mục dưới `certbot/conf/live/$DOMAIN`
5. tạo self-signed cert hoặc xin cert Let's Encrypt lần đầu
6. validate Nginx config sau khi render biến `DOMAIN`
7. build toàn bộ images
8. start hạ tầng: `postgres redis minio mosquitto`
9. chạy profile init: `minio-init db-migrate db-seed`
10. start app: `ai-serving decision-engine ingestion-service api-gateway frontend nginx`
11. in `docker compose ps` và lệnh smoke check

---

## 8. Nginx edge hiện tại

`nginx/nginx.conf` hiện tại có các điểm chính:

- HTTP `:80`:
  - phục vụ `/.well-known/acme-challenge/`
  - trả `200 ok` cho `/healthz`
  - redirect toàn bộ path còn lại sang HTTPS
- HTTPS `:443`:
  - dùng cert từ `/etc/letsencrypt/live/${DOMAIN}/`
  - bật `TLSv1.2` và `TLSv1.3`
  - thêm security headers: HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, CSP
  - rate limit `/v1/` và `/ws/`
  - proxy `/v1/` vào `api-gateway:8000`
  - proxy `/ws/` vào `api-gateway:8000` với `Upgrade`/`Connection`
  - proxy `/` vào `frontend:80`

Public port duy nhất ở VPS layer: `80`, `443`.

---

## 9. Frontend runtime hiện tại

`frontend/Dockerfile` build Vite app với build args:

- `VITE_API_BASE_URL`
- `VITE_WS_URL`

Trong `docker-compose.prod.yml`, frontend đang build với mặc định an toàn cho same-origin:

```text
VITE_API_BASE_URL=/v1
VITE_WS_URL=/ws/updates
```

Nên trên VPS, frontend không được trỏ về `http://localhost:8000` hay `ws://localhost:8000/ws/updates`.

`frontend/nginx.conf` cũng có SPA fallback qua:

```nginx
try_files $uri $uri/ /index.html;
```

Nên refresh trực tiếp route SPA vẫn lên.

---

## 10. Kiểm tra sau deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps
curl -k -I http://159.223.92.233
curl -k -I https://159.223.92.233
curl -k https://159.223.92.233/healthz
curl -k https://159.223.92.233/v1/healthz
curl -k https://159.223.92.233/v1/readyz
```

Mở browser:

```text
https://159.223.92.233
https://159.223.92.233/dashboard
https://159.223.92.233/admin
```

Kỳ vọng:

- HTTP redirect sang HTTPS
- HTTPS trả response hợp lệ
- browser có thể cảnh báo self-signed cert nếu dùng IP-only
- `/healthz` trả `ok`
- `/v1/healthz` trả backend health
- `/dashboard` và `/admin` refresh trực tiếp không 404
- browser không còn gọi `localhost:8000`
- WebSocket đi qua same-origin `/ws/updates`

Kiểm tra port public từ máy ngoài:

```bash
nc -vz 159.223.92.233 80
nc -vz 159.223.92.233 443
nc -vz 159.223.92.233 5432
nc -vz 159.223.92.233 6379
nc -vz 159.223.92.233 8000
nc -vz 159.223.92.233 9001
```

Kỳ vọng chỉ `80` và `443` mở.

---

## 11. Renew certificate

```bash
bash deploy/vps/renew_cert.sh
```

Hành vi script hiện tại:

- Nếu `DOMAIN` là IP, hoặc `TLS_CERT_MODE=self-signed`, hoặc cert hiện tại là self-signed không có renewal config: bỏ qua `certbot renew`, chỉ reload Nginx.
- Nếu là domain thật + cert Let's Encrypt: chạy `certbot/certbot renew --webroot -w /var/www/certbot`, rồi reload Nginx.

---

## 12. Lệnh thủ công khi cần debug

Build:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build
```

Start theo lớp:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d postgres redis minio mosquitto
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production --profile init up minio-init db-migrate db-seed
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d ai-serving decision-engine ingestion-service api-gateway frontend nginx
```

Validate Nginx template:

```bash
docker run --rm \
  -e DOMAIN=app.example.com \
  -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt:ro" \
  -v "$(pwd)/certbot/www:/var/www/certbot:ro" \
  nginx:1.27-alpine /bin/sh -c "envsubst '$$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf"
```

Reload Nginx:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec -T nginx /bin/sh -c "envsubst '$$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf && nginx -s reload -c /tmp/nginx.conf"
```

---

## 13. Backup tối thiểu

Postgres:

```bash
mkdir -p /opt/agmultida/backups/postgres
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > /opt/agmultida/backups/postgres/agmultida-$(date +%F-%H%M).sql
```

MinIO volume:

```bash
mkdir -p /opt/agmultida/backups/minio
docker run --rm \
  -v agmultida_minio_data:/data:ro \
  -v /opt/agmultida/backups/minio:/backup \
  alpine tar czf /backup/minio-$(date +%F-%H%M).tar.gz -C /data .
```

Config:

```bash
mkdir -p /opt/agmultida/backups/config
cp .env.production /opt/agmultida/backups/config/.env.production.$(date +%F-%H%M)
cp nginx/nginx.conf /opt/agmultida/backups/config/nginx.conf.$(date +%F-%H%M)
chmod -R go-rwx /opt/agmultida/backups
```

---

## 14. Rollback

Code rollback:

```bash
git log --oneline -n 10
git checkout <KNOWN_GOOD_COMMIT>
bash deploy/vps/deploy_vps.sh
```

Nginx config rollback:

```bash
cp /opt/agmultida/backups/config/nginx.conf.<timestamp> nginx/nginx.conf
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec -T nginx /bin/sh -c "envsubst '$$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf && nginx -s reload -c /tmp/nginx.conf"
```

Database rollback chỉ làm khi đã chốt downtime và có backup mới nhất.

---

## 15. Lỗi thường gặp

### 15.1. Nginx không tìm thấy certificate

Kiểm tra:

```bash
ls certbot/conf/live/app.example.com/
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs nginx
```

### 15.2. Frontend vẫn gọi localhost:8000

Rebuild frontend:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d frontend nginx
```

### 15.3. `/dashboard` hoặc `/admin` refresh bị 404

Kiểm tra frontend image đã build từ bản có `frontend/nginx.conf`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d frontend
```

### 15.4. WebSocket không connect

Kiểm tra:

- Nginx có `Upgrade` và `Connection` headers
- frontend dùng `/ws/updates` hoặc `wss://app.example.com/ws/updates`
- backend auth/origin policy đúng domain

### 15.5. API 502 qua Nginx

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps api-gateway frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs api-gateway nginx
```

### 15.6. Certbot renew không chạy

Kiểm tra mode hiện tại:

```bash
grep -E '^(DOMAIN|TLS_CERT_MODE|CERTBOT_EMAIL)=' .env.production
ls certbot/conf/renewal/
```

Nếu đang IP-only hoặc self-signed, đây là hành vi đúng.

---

## 16. Hardening sau khi chạy ổn

- Pin image version/digest cho production.
- Bật Docker log rotation.
- Tạo cron backup Postgres/MinIO.
- Thêm monitoring CPU/RAM/disk/container health.
- Không public MinIO console nếu chưa có policy.
- Không public Mosquitto no-auth.
- Rà `TRUSTED_HOSTS` và `CORS_ORIGINS` chỉ allow domain thật.
- Giữ `AUTH_REQUIRED=true`, `WS_REQUIRE_AUTH=true` trên môi trường public.
- Giữ `RATE_LIMIT_BACKEND=redis` trên VPS.

---

## 17. Kết luận

Flow vận hành mong muốn:

```bash
cp .env.example .env.production
# sửa .env.production
bash deploy/vps/deploy_vps.sh
```

Sau đó renew/reload cert:

```bash
bash deploy/vps/renew_cert.sh
```

Như vậy Docker Compose sẽ chạy toàn bộ project với Nginx HTTPS edge, còn các service backend/data/ML giữ private trong Docker network.