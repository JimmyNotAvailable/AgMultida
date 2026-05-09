from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'backend'))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production')
os.environ.setdefault('AUTH_REQUIRED', 'true')
os.environ.setdefault('ADMIN_RATE_LIMIT_COUNT', '2')
os.environ.setdefault('ADMIN_RATE_LIMIT_WINDOW_SECONDS', '60')

from api_gateway.main import app
from core.config import get_settings
from tests.backend.auth_helpers import auth_headers


def test_commands_require_auth():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post('/v1/commands', json={
            'zone_id': 'A01',
            'action': 'light',
            'volume_mm': 10,
            'source': 'ai_recommendation',
        })
    assert response.status_code == 401


def test_zones_status_requires_auth():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get('/v1/zones/A01/status')
    assert response.status_code == 401


def test_viewer_can_read_zones_but_cannot_command():
    get_settings.cache_clear()
    with TestClient(app) as client:
        read_response = client.get('/v1/zones', headers=auth_headers('viewer'))
        write_response = client.post('/v1/commands', headers=auth_headers('viewer'), json={
            'zone_id': 'A01',
            'action': 'light',
            'volume_mm': 10,
            'source': 'ai_recommendation',
        })
    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_cors_preflight_and_security_headers_present():
    get_settings.cache_clear()
    with TestClient(app) as client:
        preflight = client.options('/v1/zones', headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Authorization',
        })
        response = client.get('/v1/healthz')

    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == 'http://localhost:3000'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert response.headers['permissions-policy'] == 'camera=(), microphone=(), geolocation=()'


def test_websocket_rejects_missing_token():
    get_settings.cache_clear()
    with TestClient(app) as client:
        try:
            with client.websocket_connect('/ws/updates', headers={'Origin': 'http://localhost:3000'}):
                raise AssertionError('websocket should reject missing token')
        except WebSocketDisconnect as exc:
            assert exc.code == 1008


def test_websocket_accepts_valid_token_and_allowed_origin():
    get_settings.cache_clear()
    with TestClient(app) as client:
        with client.websocket_connect(
            '/ws/updates',
            headers={
                'Origin': 'http://localhost:3000',
                'Authorization': auth_headers('viewer')['Authorization'],
            },
        ) as websocket:
            assert websocket.receive_json() == {'type': 'connected', 'message': 'stub'}
            websocket.send_text('ping')
            assert websocket.receive_json() == {'type': 'echo', 'data': 'ping'}


def test_websocket_rejects_blocked_origin():
    get_settings.cache_clear()
    with TestClient(app) as client:
        try:
            with client.websocket_connect(
                '/ws/updates',
                headers={
                    'Origin': 'https://evil.example',
                    'Authorization': auth_headers('viewer')['Authorization'],
                },
            ):
                raise AssertionError('websocket should reject blocked origin')
        except WebSocketDisconnect as exc:
            assert exc.code == 1008


def test_admin_rate_limit_trips_on_repeated_command_calls():
    get_settings.cache_clear()
    with TestClient(app) as client:
        headers = auth_headers('admin', 'rate-limited-user')
        first = client.post('/v1/commands', headers=headers, json={
            'zone_id': 'A01',
            'action': 'light',
            'volume_mm': 10,
            'source': 'ai_recommendation',
        })
        second = client.post('/v1/commands', headers=headers, json={
            'zone_id': 'A01',
            'action': 'light',
            'volume_mm': 10,
            'source': 'ai_recommendation',
        })
        third = client.post('/v1/commands', headers=headers, json={
            'zone_id': 'A01',
            'action': 'light',
            'volume_mm': 10,
            'source': 'ai_recommendation',
        })
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()['error_code'] == 'RATE_LIMIT_EXCEEDED'
