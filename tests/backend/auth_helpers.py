from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt


def make_token(role: str = 'admin', subject: str = 'test-user') -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            'sub': subject,
            'role': role,
            'iss': 'agmultida',
            'aud': 'agmultida-admin',
            'iat': now,
            'exp': now + timedelta(minutes=30),
        },
        'test-secret-not-for-production',
        algorithm='HS256',
    )


def auth_headers(role: str = 'admin', subject: str = 'test-user') -> dict[str, str]:
    return {'Authorization': f'Bearer {make_token(role, subject)}'}
