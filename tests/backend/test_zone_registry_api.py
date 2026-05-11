from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production-32b')

from backend.api_gateway.main import app
from tests.backend.auth_helpers import auth_headers


def test_list_zones_returns_registry_items():
    with TestClient(app) as client:
        response = client.get('/v1/zones', headers=auth_headers('viewer'))

    assert response.status_code == 200
    body = response.json()
    assert body['zones']
    first = body['zones'][0]
    assert first['zone']['zone_id'] == 'A01'
    assert set(first['bounds']) == {'min_lng', 'min_lat', 'max_lng', 'max_lat'}
    assert len(first['centroid']) == 2
