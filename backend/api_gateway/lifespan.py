from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI

from backend.api_gateway.clients.ai_client import LiveAIClient, StubAIClient
from backend.api_gateway.clients.decision_client import LiveDecisionClient, StubDecisionClient
from backend.api_gateway.clients.ingestion_client import LiveIngestionClient, StubIngestionClient
from backend.api_gateway.dependencies import build_prediction_cache_service
from backend.core.config import get_settings
from backend.core.db import close_db_pool, open_db_pool
from backend.core.http_client import create_http_client
from backend.core.zone_status_cache import InMemoryZoneStatusCache
from backend.decision_engine.alert_engine import AlertRepository
from backend.features.alerts.service import AlertService
from backend.features.alerts.telegram_worker import TelegramWorker, TelegramWorkerConfig
from backend.features.commands.service import CommandSafetyService
from backend.features.prediction.cache import PredictionCacheService
from backend.features.prediction.service import PredictionService
from backend.features.recommendation.service import DecisionCacheService, RecommendationService
from backend.features.websocket.manager import WebSocketManager
from backend.features.websocket.redis_subscriber import RedisSubscriber
from backend.features.zones.registry import ZoneRegistryService
from backend.features.zones.status_service import ZoneStatusService

logger = logging.getLogger("agtech.gateway")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZONE_REGISTRY_PATH = PROJECT_ROOT / "metadata" / "zone_registry.csv"
ZONE_GEOJSON_PATH = PROJECT_ROOT / "metadata" / "zones.geojson"


def initialize_application_state(application: FastAPI) -> None:
    application.state.ai_client = StubAIClient()
    application.state.ingestion_client = StubIngestionClient()
    application.state.decision_client = StubDecisionClient()
    application.state.gateway_mode = "stub"
    application.state.db_enabled = False
    application.state.zone_status_cache = InMemoryZoneStatusCache(get_settings().ZONE_STATUS_CACHE_TTL_SECONDS)
    application.state.zone_registry_service = ZoneRegistryService(ZONE_REGISTRY_PATH, ZONE_GEOJSON_PATH)
    application.state.prediction_cache = PredictionCacheService()
    application.state.prediction_service = PredictionService(application.state.prediction_cache)
    application.state.decision_cache = DecisionCacheService()
    application.state.alert_service = AlertService()
    application.state.websocket_manager = WebSocketManager()
    application.state.websocket_subscriber_task = None
    application.state.recommendation_service = RecommendationService(application.state.prediction_cache, application.state.decision_cache, application.state.alert_service)
    application.state.zone_status_aggregate = ZoneStatusService(application.state.prediction_cache, application.state.decision_cache)
    application.state.command_safety_service = CommandSafetyService(application.state.prediction_cache, get_settings())
    application.state.alert_repository = AlertRepository()


async def wire_application_services(application: FastAPI) -> None:
    settings = get_settings()
    if settings.ENV == "production" and settings.ALLOW_STUBS:
        raise RuntimeError("ALLOW_STUBS must be false in production")
    if not settings.ALLOW_STUBS and settings.GATEWAY_MODE == "stub":
        raise RuntimeError("GATEWAY_MODE=stub is not allowed when ALLOW_STUBS=false")
    logger.info(
        "gateway starting",
        extra={
            "event": "gateway_startup",
            "env": settings.ENV,
            "gateway_mode": settings.GATEWAY_MODE,
            "auth_required": settings.AUTH_REQUIRED,
            "allow_stubs": settings.ALLOW_STUBS,
            "dev_auth_bypass_role": settings.DEV_AUTH_BYPASS_ROLE,
        },
    )
    if settings.GATEWAY_MODE == "live" and not settings.AI_SERVING_URL:
        raise RuntimeError("AI_SERVING_URL must be set when GATEWAY_MODE=live")

    await configure_gateway_clients(application, settings)
    await configure_storage(application)
    await configure_domain_services(application, settings)


async def configure_gateway_clients(application: FastAPI, settings) -> None:
    if settings.GATEWAY_MODE == "live":
        ai_http = create_http_client(base_url=settings.AI_SERVING_URL, timeout_ms=settings.AI_SERVING_TIMEOUT_MS)
        ingestion_http = create_http_client(base_url=settings.INGESTION_SERVICE_URL, timeout_ms=settings.INGESTION_SERVICE_TIMEOUT_MS)
        application.state.ai_client = LiveAIClient(ai_http, internal_api_key=settings.INTERNAL_API_KEY, header_name=settings.INTERNAL_API_KEY_HEADER)
        application.state.ingestion_client = LiveIngestionClient(ingestion_http, internal_api_key=settings.INTERNAL_API_KEY, header_name=settings.INTERNAL_API_KEY_HEADER)
        application.state.decision_client = LiveDecisionClient()
    else:
        application.state.ai_client = StubAIClient()
        application.state.ingestion_client = StubIngestionClient()
        application.state.decision_client = StubDecisionClient()


async def configure_storage(application: FastAPI) -> None:
    from backend.core.rate_limit import reset_rate_limiter_backend

    reset_rate_limiter_backend()
    try:
        await open_db_pool()
    except RuntimeError:
        application.state.db_enabled = False
    else:
        application.state.db_enabled = True


async def configure_domain_services(application: FastAPI, settings) -> None:
    application.state.gateway_mode = settings.GATEWAY_MODE
    application.state.zone_status_cache = InMemoryZoneStatusCache(settings.ZONE_STATUS_CACHE_TTL_SECONDS)
    application.state.zone_registry_service = ZoneRegistryService(ZONE_REGISTRY_PATH, ZONE_GEOJSON_PATH)
    application.state.prediction_cache = build_prediction_cache_service()
    application.state.prediction_service = PredictionService(application.state.prediction_cache)
    application.state.decision_cache = DecisionCacheService(application.state.prediction_cache._redis_client)
    application.state.alert_service = AlertService(application.state.prediction_cache._redis_client)
    application.state.websocket_manager = WebSocketManager()
    application.state.websocket_subscriber_task = await maybe_start_websocket_subscriber(application)
    application.state.telegram_worker_task = maybe_start_telegram_worker(application, settings)
    application.state.recommendation_service = RecommendationService(application.state.prediction_cache, application.state.decision_cache, application.state.alert_service)
    application.state.zone_status_aggregate = ZoneStatusService(application.state.prediction_cache, application.state.decision_cache, application.state.prediction_cache._redis_client)
    application.state.command_safety_service = CommandSafetyService(application.state.prediction_cache, settings)
    application.state.alert_repository = AlertRepository()


async def maybe_start_websocket_subscriber(application: FastAPI):
    if application.state.prediction_cache._redis_client is None:
        return None
    subscriber = RedisSubscriber(application.state.websocket_manager)
    return asyncio.create_task(subscriber.run_forever(application.state.prediction_cache._redis_client))


def maybe_start_telegram_worker(application: FastAPI, settings):
    if not (settings.ALERT_TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID and application.state.prediction_cache._redis_client is not None):
        return None
    telegram_worker = TelegramWorker(
        application.state.prediction_cache._redis_client,
        TelegramWorkerConfig(
            enabled=settings.ALERT_TELEGRAM_ENABLED,
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            chat_id=settings.TELEGRAM_CHAT_ID,
            api_base_url=settings.TELEGRAM_API_BASE_URL,
            consumer_group=settings.TELEGRAM_CONSUMER_GROUP,
            consumer_name=settings.TELEGRAM_CONSUMER_NAME,
            max_retries=settings.TELEGRAM_MAX_RETRIES,
            block_ms=settings.TELEGRAM_BLOCK_MS,
            backoff_base_seconds=settings.TELEGRAM_BACKOFF_BASE_SECONDS,
        ),
    )
    return asyncio.create_task(telegram_worker.run_forever())


async def shutdown_application_services(application: FastAPI) -> None:
    websocket_subscriber_task = getattr(application.state, "websocket_subscriber_task", None)
    if websocket_subscriber_task is not None:
        websocket_subscriber_task.cancel()
    telegram_task = getattr(application.state, "telegram_worker_task", None)
    if telegram_task is not None:
        telegram_task.cancel()
    if hasattr(application.state, "ai_client") and hasattr(application.state.ai_client, "close"):
        await application.state.ai_client.close()
    if hasattr(application.state, "ingestion_client") and hasattr(application.state.ingestion_client, "close"):
        await application.state.ingestion_client.close()
    application.state.ai_client = StubAIClient()
    application.state.ingestion_client = StubIngestionClient()
    application.state.decision_client = StubDecisionClient()
    application.state.gateway_mode = "stub"
    await close_db_pool()
