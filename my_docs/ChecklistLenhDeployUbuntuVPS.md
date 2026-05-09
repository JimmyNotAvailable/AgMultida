# Checklist Lệnh Deploy Ubuntu VPS

Thay các giá trị sau trước khi chạy:

- `159.223.92.233`
- `<REPO_URL>`
- `<strong-password>`
- `<strong-access-key>`
- `<strong-secret-key>`
- `<random-256-bit-secret>`
- `<random-salt>`
- `<random-internal-key-16+-chars>`
- `<your-domain>` nếu dùng domain thật + Let's Encrypt

---

## 1. Cài Docker và mở firewall

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
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Đăng xuất rồi đăng nhập lại.

Không mở public các port nội bộ: `5432`, `6379`, `8000`, `8001`, `8002`, `8003`, `9000`, `9001`, `1883`.

---

## 2. Clone repo và chuẩn bị workspace

```bash
sudo mkdir -p /opt/agmultida
sudo chown -R $USER:$USER /opt/agmultida
git clone <REPO_URL> /opt/agmultida/app
cd /opt/agmultida/app
mkdir -p certbot/conf certbot/www
cp .env.example .env.production
chmod 600 .env.production
```

---

## 3. Sửa cấu hình production

### 3.1. Mẫu IP-only, self-signed

Sửa `.env.production` tối thiểu:

```text
POSTGRES_DB=agtech
POSTGRES_USER=agtech
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

### 3.2. Mẫu domain thật, Let's Encrypt

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

### 3.3. Điểm cần nhớ

- `deploy/vps/deploy_vps.sh` sẽ chặn placeholder kiểu `CHANGE_ME*`, `your_*`, `test`, `test-*`.
- `VITE_API_BASE_URL` chỉ nên là `/v1` hoặc `https://...`.
- `VITE_WS_URL` chỉ nên là `/ws/updates` hoặc `wss://...`.
- Nếu `DOMAIN` là IPv4, script tự ép sang `self-signed` dù `TLS_CERT_MODE` đặt gì.
- Không cần sửa tay `nginx/nginx.conf` nếu `DOMAIN` trong `.env.production` đúng.

---

## 4. Deploy bằng một lệnh

```bash
bash deploy/vps/deploy_vps.sh
```

Script sẽ tự:

1. kiểm tra `docker`, `python3`, `.env.production`, compose files, `nginx/nginx.conf`
2. đọc env bắt buộc và chặn placeholder
3. tạo `certbot/conf`, `certbot/www`, `certbot/conf/live/$DOMAIN`
4. tạo self-signed cert lần đầu, hoặc xin cert Let's Encrypt nếu dùng domain thật
5. validate nginx config sau khi render `DOMAIN`
6. build toàn bộ images
7. start infra: `postgres redis minio mosquitto`
8. chạy init profile: `minio-init db-migrate db-seed`
9. start app: `ai-serving decision-engine ingestion-service api-gateway frontend nginx`
10. in `docker compose ps` và lệnh smoke check

Kiểm tra cert sau deploy:

```bash
ls certbot/conf/live/159.223.92.233/
```

Nếu dùng domain thật:

```bash
ls certbot/conf/live/<your-domain>/
```

---

## 5. Validate Nginx config thủ công nếu cần

```bash
docker run --rm \
  -e DOMAIN=159.223.92.233 \
  -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt:ro" \
  -v "$(pwd)/certbot/www:/var/www/certbot:ro" \
  nginx:1.27-alpine /bin/sh -c "envsubst '$$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf"
```

---

## 6. Build và khởi động stack thủ công nếu cần

Bình thường không cần phần này vì `deploy/vps/deploy_vps.sh` đã làm đủ. Khi cần debug thủ công:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d postgres redis minio mosquitto

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production --profile init up minio-init db-migrate db-seed

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d ai-serving decision-engine ingestion-service api-gateway frontend nginx
```

---

## 7. Kiểm tra sau deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs -f nginx api-gateway frontend

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
- `/healthz` trả `ok`
- `/v1/healthz` và `/v1/readyz` lên
- frontend refresh trực tiếp `/dashboard` và `/admin` không 404
- frontend không còn gọi `http://localhost:8000`
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

## 8. Reload Nginx sau khi đổi cert/config

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec -T nginx /bin/sh -c "envsubst '$$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf && nginx -s reload -c /tmp/nginx.conf"
```

---

## 9. Renew certificate

```bash
bash deploy/vps/renew_cert.sh
```

Hành vi hiện tại:

- IP-only hoặc `self-signed`: bỏ qua `certbot renew`, chỉ reload Nginx an toàn.
- Domain thật + Let's Encrypt: chạy `certbot renew --webroot -w /var/www/certbot`, rồi reload Nginx.

---

## 10. Lỗi hay gặp

### 10.1. Script báo placeholder

Kiểm tra lại các biến:

- `POSTGRES_PASSWORD`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `JWT_SECRET`
- `API_KEY_HASH_SALT`
- `VITE_API_BASE_URL`
- `VITE_WS_URL`
- `DOMAIN`
- `CERTBOT_EMAIL` nếu dùng Let's Encrypt

### 10.2. Nginx không lên vì thiếu cert

```bash
ls certbot/conf/live/159.223.92.233/
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs nginx
```

### 10.3. Frontend vẫn gọi localhost:8000

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d frontend nginx
```

### 10.4. `/dashboard` hoặc `/admin` refresh bị 404

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d frontend
```

### 10.5. WebSocket không connect

Kiểm tra:

- frontend dùng `/ws/updates` hoặc `wss://<your-domain>/ws/updates`
- Nginx có `Upgrade` và `Connection` headers
- backend auth/origin policy đúng domain

### 10.6. API 502 qua Nginx

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps api-gateway frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs api-gateway nginx
```