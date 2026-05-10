from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.schemas import ConfidenceFlag, PredictResponse
from backend.features.prediction.cache import PredictionCacheService
from backend.features.prediction.policy import apply_prediction_policy


class FailingRedis:
    async def get(self, key: str):
        raise RuntimeError('redis down')

    async def set(self, key: str, value: str, ex: int):
        raise RuntimeError('redis down')

    async def delete(self, key: str):
        raise RuntimeError('redis down')


class CorruptRedis:
    deleted: str | None = None

    async def get(self, key: str):
        return '{bad-json'

    async def set(self, key: str, value: str, ex: int):
        return None

    async def delete(self, key: str):
        self.deleted = key
        return None


def make_prediction(**overrides) -> PredictResponse:
    data = {
        'zone_id': 'A01',
        'timestamp': datetime(2026, 5, 10, 10, 15, tzinfo=timezone.utc),
        'stress_prob': 0.42,
        'uncertainty': 0.12,
        'confidence_flag': ConfidenceFlag.HIGH,
        'degraded_mode': False,
        'attention_weights': [0.4, 0.3, 0.3],
        'model_version': 'v1',
        'latency_ms': 42.0,
    }
    data.update(overrides)
    return PredictResponse(**data)


@pytest.mark.anyio
async def test_prediction_cache_stores_latest_and_bucket_with_memory_fallback():
    cache = PredictionCacheService(redis_client=FailingRedis())
    prediction = make_prediction()

    await cache.store_success(prediction, 'live')

    latest = await cache.get_latest('A01')
    bucket = await cache.get_bucket('A01', prediction.timestamp.isoformat())
    assert latest is not None
    assert bucket is not None
    assert latest.response.zone_id == 'A01'
    assert bucket.model_version == 'v1'
    assert latest.source == 'live'


@pytest.mark.anyio
async def test_prediction_cache_ignores_corrupt_redis_payload():
    redis = CorruptRedis()
    cache = PredictionCacheService(redis_client=redis)

    latest = await cache.get_latest('A01')

    assert latest is None
    assert redis.deleted == 'pred:A01:latest'


def test_prediction_policy_degrades_slow_prediction():
    prediction = make_prediction(latency_ms=650.0)

    result = apply_prediction_policy(prediction, latency_ms=650.0, source='live')

    assert result.degraded_mode is True
    assert result.confidence_flag == ConfidenceFlag.LOW


def test_prediction_policy_penalizes_missing_modality():
    prediction = make_prediction(uncertainty=0.2)

    result = apply_prediction_policy(prediction, latency_ms=100.0, source='live', missing_modality_count=1)

    assert result.uncertainty == 0.35
    assert result.confidence_flag == ConfidenceFlag.LOW
