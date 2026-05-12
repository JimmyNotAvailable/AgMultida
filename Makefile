# Makefile — AgMultida local Docker management
# Usage: make <target>
# Requires: docker compose v2 (bundled with Docker Desktop)

.PHONY: help build up down restart logs status init db-migrate db-seed \
        minio-init shell-api shell-db clean reset

# ── Default ──────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "AgMultida Docker Commands"
	@echo "========================="
	@echo "  make build        Build all Docker images"
	@echo "  make init         Migrate DB + seed zones + init MinIO (run once)"
	@echo "  make up           Start all services"
	@echo "  make down         Stop all services"
	@echo "  make restart      Rebuild images and restart all services"
	@echo "  make logs         Tail logs from all services"
	@echo "  make status       Show health of all containers"
	@echo ""
	@echo "  make db-migrate   Run Alembic migrations only"
	@echo "  make db-seed      Seed zone registry only"
	@echo "  make minio-init   Create MinIO buckets only"
	@echo ""
	@echo "  make shell-api    Bash shell inside api-gateway container"
	@echo "  make shell-db     psql inside postgres container"
	@echo "  make clean        Remove containers and networks (keep volumes)"
	@echo "  make reset        Remove EVERYTHING including pg_data / minio volumes"
	@echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	docker compose build

# ── One-time setup (migrations + seed + minio buckets) ───────────────────────
init: db-migrate db-seed minio-init

db-migrate:
	docker compose --profile init run --rm db-migrate

db-seed:
	docker compose --profile init run --rm db-seed

minio-init:
	docker compose --profile init run --rm minio-init

# ── Lifecycle ─────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down
	docker compose build
	docker compose up -d

# ── Observability ─────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

status:
	docker compose ps

# ── Debug shells ─────────────────────────────────────────────────────────────
shell-api:
	docker compose exec api-gateway bash

shell-db:
	docker compose exec postgres psql -U agtech -d agtech

# ── Teardown ─────────────────────────────────────────────────────────────────
clean:
	docker compose down --remove-orphans

reset:
	docker compose down -v --remove-orphans
