#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE=${ENV_FILE:-"$REPO_ROOT/.env.production"}
COMPOSE_ARGS=(-f "$REPO_ROOT/docker-compose.yml" -f "$REPO_ROOT/docker-compose.prod.yml" --env-file "$ENV_FILE")
CERTBOT_CONF_DIR="$REPO_ROOT/certbot/conf"
CERTBOT_WEBROOT_DIR="$REPO_ROOT/certbot/www"
LOCK_DIR="$REPO_ROOT/.renew-cert.lock"
CERTBOT_CONF_DIR="$REPO_ROOT/certbot/conf"
TLS_CERT_MODE=''
DOMAIN_IS_IP='false'

log() {
  printf '[CERT] %s\n' "$1"
}

fail() {
  printf '[CERT] ERROR: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  rm -rf "$LOCK_DIR"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

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

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

is_ipv4_address() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

reload_nginx() {
  local domain=$1
  compose exec -T nginx /bin/sh -c "envsubst '\$DOMAIN' < /etc/nginx/nginx.conf > /tmp/nginx.conf && nginx -t -c /tmp/nginx.conf && nginx -s reload -c /tmp/nginx.conf"
}

main() {
  require_command docker
  require_command python3
  [[ -f "$ENV_FILE" ]] || fail "Missing env file: $ENV_FILE"
  mkdir "$LOCK_DIR" 2>/dev/null || fail "Renewal already in progress"
  trap cleanup EXIT

  local domain
  domain=$(read_env_value DOMAIN || true)
  [[ -n "$domain" ]] || fail "Missing DOMAIN in $ENV_FILE"

  TLS_CERT_MODE=$(read_env_value TLS_CERT_MODE || true)
  TLS_CERT_MODE=${TLS_CERT_MODE:-}
  if is_ipv4_address "$domain"; then
    DOMAIN_IS_IP='true'
  fi

  mkdir -p "$CERTBOT_CONF_DIR" "$CERTBOT_WEBROOT_DIR"

  if [[ "$DOMAIN_IS_IP" == 'true' || "${TLS_CERT_MODE,,}" == 'self-signed' || -f "$CERTBOT_CONF_DIR/live/$domain/fullchain.pem" && ! -f "$CERTBOT_CONF_DIR/renewal/$domain.conf" ]]; then
    log "Skipping certbot renew for self-signed or IP-based certificate"
    reload_nginx "$domain"
    log "Nginx reloaded"
    return
  fi

  log "Renewing certificates via webroot"
  docker run --rm \
    -v "$CERTBOT_CONF_DIR:/etc/letsencrypt" \
    -v "$CERTBOT_WEBROOT_DIR:/var/www/certbot" \
    certbot/certbot renew --webroot -w /var/www/certbot

  log "Reloading nginx after renewal"
  reload_nginx "$domain"
  log "Certificate renewal completed"
}

main "$@"
