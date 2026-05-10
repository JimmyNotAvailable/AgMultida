from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from backend.api_gateway.main import app
from tests.backend.auth_helpers import auth_headers


def test_zone_list_returns_registry_backed_rows():
    with TestClient(app) as client:
        response = client.get('/v1/zones', headers=auth_headers('viewer'))

    assert response.status_code == 200
    body = response.json()
    assert 'trace_id' in body
    assert [item['zone']['zone_id'] for item in body['zones']] == ['A01', 'A02', 'A03', 'D01', 'E01', 'F01']
    assert body['zones'][0]['zone']['zone_name'] == 'An Giang validation zone A01'
    assert body['zones'][0]['zone']['province'] == 'An Giang'
    assert body['zones'][0]['zone']['crop_type'] == 'rice'
    assert body['zones'][0]['zone']['split'] == 'train'
    assert body['zones'][0]['zone']['local_timezone'] == 'Asia/Ho_Chi_Minh'
    assert 'latest_telemetry' not in body['zones'][0]
    assert 'notes' not in body['zones'][0]['zone']
