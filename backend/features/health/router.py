from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from backend.core.config import get_settings
from backend.core.db import check_database_ready
from backend.core.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/v1/healthz", response_model=HealthResponse)
async def healthz():
    return HealthResponse()


@router.get("/v1/readyz")
async def readyz(request: Request):
    mode = getattr(request.app.state, "gateway_mode", "unknown")
    checked_at = datetime.now(timezone.utc).isoformat()
    settings = get_settings()
    decision_dep = {"status": "stub"} if mode == "stub" else {"status": "in_process", "checked_at": checked_at}
    telegram_dep = build_telegram_readiness(settings, getattr(request.app.state, "telegram_worker_task", None))
    database_dep = {"status": "disabled"}
    if request.app.state.db_enabled:
        database = await check_database_ready()
        database_dep = {
            "status": database["status"],
            "checked_at": checked_at,
            "details": database["details"],
        }

    if mode == "stub":
        overall = "ok" if database_dep["status"] in {"ok", "disabled"} and telegram_dep["status"] != "degraded" else "degraded"
        return {
            "status": overall,
            "mode": mode,
            "dependencies": {
                "database": database_dep,
                "ai_serving": {"status": "stub", "checked_at": checked_at},
                "ingestion_service": {"status": "stub", "checked_at": checked_at},
                "decision_engine": decision_dep,
                "telegram": telegram_dep,
            },
        }

    ai_ready = await request.app.state.ai_client.ready()
    ingestion_ready = await request.app.state.ingestion_client.ready()
    ai_dep = {
        "status": ai_ready.get("status", "degraded"),
        "checked_at": checked_at,
        "model_loaded": ai_ready.get("model_loaded"),
        "manifest_loaded": ai_ready.get("manifest_loaded"),
        "upstream_last_error": "Dependency unavailable" if ai_ready.get("upstream_last_error") else None,
    }
    ingestion_dep = {
        "status": ingestion_ready.get("status", "degraded"),
        "checked_at": checked_at,
        "database": ingestion_ready.get("database"),
    }
    gateway_status = "ok" if ai_dep["status"] == "ok" and database_dep["status"] in {"ok", "disabled"} and telegram_dep["status"] != "degraded" else "degraded"
    return {
        "status": gateway_status,
        "mode": mode,
        "dependencies": {
            "database": database_dep,
            "ai_serving": ai_dep,
            "ingestion_service": ingestion_dep,
            "decision_engine": decision_dep,
            "telegram": telegram_dep,
        },
    }


def build_telegram_readiness(settings, worker_task):
    if not settings.ALERT_TELEGRAM_ENABLED:
        return {"status": "disabled"}
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return {"status": "degraded", "reason": "missing_config"}
    if worker_task is None:
        return {"status": "degraded", "reason": "worker_not_running"}
    return {"status": "ok"}
