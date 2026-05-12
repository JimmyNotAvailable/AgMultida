from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production-32b')
os.environ.setdefault('INTERNAL_API_KEY', 'test-internal-key-123456')

from backend.ingestion_service.main import app  # noqa: E402
from tests.contract_fixtures import VALID_TELEMETRY_REQUEST  # noqa: E402


def test_ingestion_readyz_reports_database_dependency():
    with TestClient(app) as client:
        response = client.get('/readyz')
        assert response.status_code == 200
        body = response.json()
        assert 'database' in body['dependencies']


def test_internal_telemetry_rejects_empty_measurements():
    payload = {
        'device_id': 'iot_sensor_001',
        'zone_id': 'A01',
        'timestamp': '2024-02-14T03:00:00Z',
        'measurements': {},
    }
    with TestClient(app) as client:
        response = client.post(
            '/internal/telemetry',
            json=payload,
            headers={'X-Internal-API-Key': 'test-internal-key-123456'},
        )
        assert response.status_code == 422
        assert response.json()['error_code'] == 'TELEMETRY_REJECTED'


def test_internal_telemetry_rejects_missing_internal_api_key():
    with TestClient(app) as client:
        response = client.post('/internal/telemetry', json=VALID_TELEMETRY_REQUEST)
        assert response.status_code == 401
        assert response.json()['error_code'] == 'AUTH_INVALID_API_KEY'


def test_internal_telemetry_accepts_valid_payload_when_database_available():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return

    with TestClient(app) as client:
        response = client.post(
            '/internal/telemetry',
            json=VALID_TELEMETRY_REQUEST,
            headers={'X-Internal-API-Key': 'test-internal-key-123456'},
        )
        assert response.status_code == 200
        body = response.json()
        assert body['accepted'] is True
        assert body['sample_id'].endswith('_iot_sensor_001')
