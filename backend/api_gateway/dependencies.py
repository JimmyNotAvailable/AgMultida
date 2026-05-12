from __future__ import annotations

from fastapi import Depends

from backend.core.config import get_settings
from backend.core.rate_limit import create_rate_limit_dependency
from backend.core.security import require_role
from backend.features.prediction.cache import PredictionCacheService

admin_read_dependency = Depends(require_role("viewer", "operator", "admin"))
admin_write_dependency = Depends(require_role("operator", "admin"))
admin_mutation_dependency = Depends(create_rate_limit_dependency("admin"))
zone_read_limit_dependency = Depends(create_rate_limit_dependency("zones"))

ADMIN_READ_DEPENDENCIES = [admin_read_dependency, zone_read_limit_dependency]
ADMIN_WRITE_DEPENDENCIES = [admin_write_dependency, admin_mutation_dependency]


def build_prediction_cache_service() -> PredictionCacheService:
    settings = get_settings()
    redis_client = None
    if settings.REDIS_URL:
        try:
            from redis import asyncio as redis_asyncio
        except ImportError:
            redis_client = None
        else:
            redis_client = redis_asyncio.from_url(settings.REDIS_URL)
    return PredictionCacheService(redis_client=redis_client)
