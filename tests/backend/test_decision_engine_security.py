from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production')
os.environ.setdefault('INTERNAL_API_KEY', 'test-internal-key-123456')

from backend.decision_engine.main import app  # noqa: E402


VALID_RECOMMEND_PAYLOAD = {
    'zone_id': 'A01',
    'stress_prob': 0.65,
    'uncertainty': 0.10,
    'soil_moisture': 22.0,
    'rain_forecast_3h': 0.1,
}


def test_internal_recommend_rejects_missing_internal_api_key():
    with TestClient(app) as client:
        response = client.post('/internal/recommend', json=VALID_RECOMMEND_PAYLOAD)
    assert response.status_code == 401
    assert response.json()['error_code'] == 'AUTH_INVALID_API_KEY'


def test_internal_recommend_accepts_valid_internal_api_key():
    with TestClient(app) as client:
        response = client.post(
            '/internal/recommend',
            json=VALID_RECOMMEND_PAYLOAD,
            headers={'X-Internal-API-Key': 'test-internal-key-123456'},
        )
    assert response.status_code == 200
    assert response.json()['action'] == 'heavy'
