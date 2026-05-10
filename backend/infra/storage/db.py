from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.core.config import get_settings

_DB_POOL: ConnectionPool | None = None


def _open_db_pool_sync() -> ConnectionPool:
    global _DB_POOL
    if _DB_POOL is not None:
        return _DB_POOL

    settings = get_settings()
    if not settings.DATABASE_URL:
        raise RuntimeError('DATABASE_URL must be set before opening database pool')

    _DB_POOL = ConnectionPool(
        conninfo=settings.DATABASE_URL,
        min_size=settings.DB_POOL_MIN_SIZE,
        max_size=settings.DB_POOL_MAX_SIZE,
        open=True,
        kwargs={
            'autocommit': False,
            'row_factory': dict_row,
            'connect_timeout': settings.DB_CONNECT_TIMEOUT_SECONDS,
        },
    )
    _DB_POOL.wait()
    return _DB_POOL


async def open_db_pool() -> ConnectionPool:
    return await asyncio.to_thread(_open_db_pool_sync)


def _close_db_pool_sync() -> None:
    global _DB_POOL
    if _DB_POOL is None:
        return
    _DB_POOL.close()
    _DB_POOL = None


async def close_db_pool() -> None:
    await asyncio.to_thread(_close_db_pool_sync)


def get_db_pool() -> ConnectionPool:
    if _DB_POOL is None:
        raise RuntimeError('Database pool has not been opened')
    return _DB_POOL


@contextmanager
def db_connection() -> Any:
    pool = get_db_pool()
    with pool.connection() as connection:
        yield connection


def _check_database_ready_sync() -> dict[str, Any]:
    try:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 AS ok')
                row = cursor.fetchone()
        return {'status': 'ok', 'details': row or {'ok': 1}}
    except Exception as exc:
        return {'status': 'degraded', 'details': {'error': str(exc)}}


async def check_database_ready() -> dict[str, Any]:
    return await asyncio.to_thread(_check_database_ready_sync)


def _fetch_one_sync(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


async def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return await asyncio.to_thread(_fetch_one_sync, query, params)


def _fetch_all_sync(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


async def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_all_sync, query, params)


def _execute_sync(query: str, params: tuple[Any, ...] = ()) -> None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
        connection.commit()


async def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    await asyncio.to_thread(_execute_sync, query, params)


def _execute_returning_sync(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        connection.commit()
        return row


async def execute_returning(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return await asyncio.to_thread(_execute_returning_sync, query, params)


async def ensure_device_registered(device_id: str, zone_id: str) -> None:
    await execute(
        '''
        INSERT INTO devices (device_id, zone_id)
        VALUES (%s, %s)
        ON CONFLICT (device_id) DO UPDATE
        SET zone_id = EXCLUDED.zone_id,
            updated_at = now()
        ''',
        (device_id, zone_id),
    )
