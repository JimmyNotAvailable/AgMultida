#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE=${ENV_FILE:-"$REPO_ROOT/.env.production"}
COMPOSE_ARGS=(-f "$REPO_ROOT/docker-compose.yml" -f "$REPO_ROOT/docker-compose.prod.yml" --env-file "$ENV_FILE")
CERTBOT_CONF_DIR="$REPO_ROOT/certbot/conf"
CERTBOT_WEBROOT_DIR="$REPO_ROOT/certbot/www"

log() { printf '[DEPLOY] %s\n' "$1"; }
fail() { printf '[DEPLOY] ERROR: %s\n' "$1" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"; }
require_file() { [[ -f "$1" ]] || fail "Required file not found: $1"; }

read_env_value() {
  python3 - "$ENV_FILE" "$1" <<'PY'
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
for raw_line in env_path.read_text(encoding='utf-8').splitlines():
    line = raw_line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    current_key, value = line.split('=', 1)
    if current_key.strip() != key:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    print(value)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

assert_not_placeholder() {
  local key=$1
  local value=$2
  local lowered=${value,,}

  [[ -n "$value" ]] || fail "Missing value for $key in $ENV_FILE"
  case "$lowered" in
    change_me*|*changeme*|your_*|test|test-* )
      fail "Placeholder value detected for $key in $ENV_FILE"
      ;;
  esac
}

is_ipv4_address() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

DOMAIN=''
TLS_CERT_MODE=''
CERTBOT_EMAIL=''
POSTGRES_PASSWORD=''
MINIO_ACCESS_KEY=''
MINIO_SECRET_KEY=''
JWT_SECRET=''
API_KEY_HASH_SALT=''
VITE_API_BASE_URL=''
VITE_WS_URL=''
SELF_SIGNED_CERT_DAYS='365'
CERT_DIR=''
CERT_PATH=''
KEY_PATH=''
CERT_MODE=''
DOMAIN_IS_IP='false'

load_required_env() {
  DOMAIN=$(read_env_value DOMAIN || true)
  TLS_CERT_MODE=$(read_env_value TLS_CERT_MODE || true)
  CERTBOT_EMAIL=$(read_env_value CERTBOT_EMAIL || true)
  POSTGRES_PASSWORD=$(read_env_value POSTGRES_PASSWORD || true)
  MINIO_ACCESS_KEY=$(read_env_value MINIO_ACCESS_KEY || true)
  MINIO_SECRET_KEY=$(read_env_value MINIO_SECRET_KEY || true)
  JWT_SECRET=$(read_env_value JWT_SECRET || true)
  API_KEY_HASH_SALT=$(read_env_value API_KEY_HASH_SALT || true)
  VITE_API_BASE_URL=$(read_env_value VITE_API_BASE_URL || true)
  VITE_WS_URL=$(read_env_value VITE_WS_URL || true)
  SELF_SIGNED_CERT_DAYS=$(read_env_value SELF_SIGNED_CERT_DAYS || true)
  SELF_SIGNED_CERT_DAYS=${SELF_SIGNED_CERT_DAYS:-365}

  assert_not_placeholder DOMAIN "$DOMAIN"
  assert_not_placeholder POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
  assert_not_placeholder MINIO_ACCESS_KEY "$MINIO_ACCESS_KEY"
  assert_not_placeholder MINIO_SECRET_KEY "$MINIO_SECRET_KEY"
  assert_not_placeholder JWT_SECRET "$JWT_SECRET"
  assert_not_placeholder API_KEY_HASH_SALT "$API_KEY_HASH_SALT"
  assert_not_placeholder VITE_API_BASE_URL "$VITE_API_BASE_URL"
  assert_not_placeholder VITE_WS_URL "$VITE_WS_URL"

  [[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || fail "DOMAIN has invalid format: $DOMAIN"
  [[ "$VITE_API_BASE_URL" == /v1 || "$VITE_API_BASE_URL" == https://* ]] || fail "VITE_API_BASE_URL should be /v1 or https://..."
  [[ "$VITE_WS_URL" == /ws/updates || "$VITE_WS_URL" == wss://* ]] || fail "VITE_WS_URL should be /ws/updates or wss://..."

  if is_ipv4_address "$DOMAIN"; then
    DOMAIN_IS_IP='true'
  fi

  if [[ "${TLS_CERT_MODE,,}" == 'letsencrypt' ]]; then
    CERT_MODE='letsencrypt'
  else
    CERT_MODE='self-signed'
  fi

  if [[ "$DOMAIN_IS_IP" == 'true' ]]; then
    CERT_MODE='self-signed'
  fi

  if [[ "$CERT_MODE" == 'letsencrypt' ]]; then
    [[ -n "$CERTBOT_EMAIL" ]] || fail "Missing CERTBOT_EMAIL in $ENV_FILE for Let's Encrypt mode"
    case "${CERTBOT_EMAIL,,}" in
      admin@example.com|example.com|localhost)
        fail "Placeholder value detected for CERTBOT_EMAIL in $ENV_FILE"
        ;;
    esac
  fi

  CERT_DIR="$CERTBOT_CONF_DIR/live/$DOMAIN"
  CERT_PATH="$CERT_DIR/fullchain.pem"
  KEY_PATH="$CERT_DIR/privkey.pem"
}

ensure_certificate_dirs() {
  mkdir -p "$CERTBOT_CONF_DIR" "$CERTBOT_WEBROOT_DIR" "$CERT_DIR"
}

generate_self_signed_certificate() {
  require_command openssl

  local subject_alt_name
  if [[ "$DOMAIN_IS_IP" == 'true' ]]; then
    subject_alt_name="subjectAltName=IP:$DOMAIN"
  else
    subject_alt_name="subjectAltName=DNS:$DOMAIN"
  fi

  log "Generating self-signed certificate for $DOMAIN"
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY_PATH" \
    -out "$CERT_PATH" \
    -days "$SELF_SIGNED_CERT_DAYS" \
    -subj "/CN=$DOMAIN" \
    -addext "$subject_alt_name"
}

ensure_initial_certificate() {
  if [[ -f "$CERT_PATH" && -f "$KEY_PATH" ]]; then
    log "Existing certificate found for $DOMAIN"
    return
  fi

  if [[ "$CERT_MODE" == 'letsencrypt' ]]; then
    log "Issuing initial Let's Encrypt certificate for $DOMAIN"
    docker run --rm \
      -p 80:80 \
      -v "$CERTBOT_CONF_DIR:/etc/letsencrypt" \
      -v "$CERTBOT_WEBROOT_DIR:/var/www/certbot" \
      certbot/certbot certonly --standalone \
      -d "$DOMAIN" \
      --email "$CERTBOT_EMAIL" \
      --agree-tos \
      --no-eff-email
    return
  fi

  generate_self_signed_certificate
}

validate_nginx_template() {
  log "Validating rendered Nginx config"
  docker run --rm \
    -e DOMAIN="$DOMAIN" \
    -v "$REPO_ROOT/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
    -v "$CERTBOT_CONF_DIR:/etc/letsencrypt:ro" \
    -v "$CERTBOT_WEBROOT_DIR:/var/www/certbot:ro" \
    nginx:1.27-alpine /bin/sh -c "envsubst '\$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf"
}

main() {
  require_command docker
  require_command python3
  require_file "$ENV_FILE"
  require_file "$REPO_ROOT/docker-compose.yml"
  require_file "$REPO_ROOT/docker-compose.prod.yml"
  require_file "$REPO_ROOT/nginx/nginx.conf"

  load_required_env
  ensure_certificate_dirs
  ensure_initial_certificate
  validate_nginx_template

  log "Using $CERT_MODE HTTPS certificate for $DOMAIN"
  log "Building production images"
  compose build

  log "Starting infrastructure services"
  compose up -d postgres redis minio mosquitto

  log "Running initialization profile"
  compose --profile init up minio-init db-migrate db-seed

  log "Starting application services"
  compose up -d ai-serving decision-engine ingestion-service api-gateway frontend nginx

  log "Deployment complete. Current status:"
  compose ps
  printf '\n[DEPLOY] Smoke checks:\n'
  printf '  curl -k -I https://%s/\n' "$DOMAIN"
  printf '  curl -k https://%s/healthz\n' "$DOMAIN"
  printf '  curl -k https://%s/v1/healthz\n' "$DOMAIN"
}

main "$@"
