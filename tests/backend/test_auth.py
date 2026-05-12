from __future__ import annotations

import os
import sys
from pathlib import Path

import jwt
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ.setdefault('JWT_SECRET', 'test-secret-not-for-production-32b')
os.environ.setdefault('AUTH_REQUIRED', 'true')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('ADMIN_USERNAME', 'admin')
os.environ.setdefault('ADMIN_PASSWORD', 'admin123@')

from backend.api_gateway.main import app
from backend.core.config import get_settings


LOGIN_PATH = '/v1/auth/login'
REFRESH_PATH = '/v1/auth/refresh'
ME_PATH = '/v1/auth/me'


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )


def test_login_returns_access_and_refresh_tokens_for_valid_dev_credentials():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(LOGIN_PATH, json={'username': 'admin', 'password': 'admin123@'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['token_type'] == 'bearer'
    assert payload['username'] == 'admin'
    assert payload['role'] == 'admin'
    assert isinstance(payload['expires_in'], int)
    assert payload['expires_in'] > 0
    assert payload['access_token']
    assert payload['refresh_token']
    assert 'password' not in payload

    access_claims = decode_token(payload['access_token'])
    refresh_claims = decode_token(payload['refresh_token'])
    assert access_claims['sub'] == 'admin'
    assert access_claims['role'] == 'admin'
    assert access_claims['type'] == 'access'
    assert refresh_claims['sub'] == 'admin'
    assert refresh_claims['role'] == 'admin'
    assert refresh_claims['type'] == 'refresh'


def test_login_rejects_invalid_password_with_generic_error():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(LOGIN_PATH, json={'username': 'admin', 'password': 'wrong-pass'})

    assert response.status_code == 401
    payload = response.json()
    assert payload['message'] == 'Invalid credentials'


def test_login_rejects_unknown_user_with_generic_error():
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(LOGIN_PATH, json={'username': 'someone-else', 'password': 'admin123@'})

    assert response.status_code == 401
    payload = response.json()
    assert payload['message'] == 'Invalid credentials'


def test_refresh_returns_new_token_pair_for_valid_refresh_token():
    get_settings.cache_clear()
    with TestClient(app) as client:
        login_response = client.post(LOGIN_PATH, json={'username': 'admin', 'password': 'admin123@'})
        refresh_response = client.post(REFRESH_PATH, json={'refresh_token': login_response.json()['refresh_token']})

    assert refresh_response.status_code == 200
    payload = refresh_response.json()
    assert payload['access_token']
    assert payload['refresh_token']
    assert payload['access_token'] != login_response.json()['access_token']

    access_claims = decode_token(payload['access_token'])
    assert access_claims['type'] == 'access'
    assert access_claims['sub'] == 'admin'


def test_refresh_rejects_access_token():
    get_settings.cache_clear()
    with TestClient(app) as client:
        login_response = client.post(LOGIN_PATH, json={'username': 'admin', 'password': 'admin123@'})
        refresh_response = client.post(REFRESH_PATH, json={'refresh_token': login_response.json()['access_token']})

    assert refresh_response.status_code == 401
    assert refresh_response.json()['message'] == 'Invalid token'


def test_me_requires_valid_bearer_token():
    get_settings.cache_clear()
    with TestClient(app) as client:
        unauthorized = client.get(ME_PATH)
        login_response = client.post(LOGIN_PATH, json={'username': 'admin', 'password': 'admin123@'})
        token = login_response.json()['access_token']
        authorized = client.get(ME_PATH, headers={'Authorization': f'Bearer {token}'})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()['username'] == 'admin'
    assert authorized.json()['role'] == 'admin'
