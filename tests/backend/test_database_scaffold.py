from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_alembic_files_exist():
    assert (PROJECT_ROOT / 'alembic.ini').exists()
    assert (PROJECT_ROOT / 'migrations' / 'env.py').exists()
    assert (PROJECT_ROOT / 'migrations' / 'versions' / '0001_initial_schema.py').exists()


def test_initial_migration_defines_core_tables():
    migration = (PROJECT_ROOT / 'migrations' / 'versions' / '0001_initial_schema.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS users' in migration
    assert 'CREATE TABLE IF NOT EXISTS zones' in migration
    assert 'CREATE TABLE IF NOT EXISTS devices' in migration
    assert 'CREATE TABLE IF NOT EXISTS sensor_telemetry' in migration
    assert 'CREATE TABLE IF NOT EXISTS predictions' in migration
    assert 'CREATE TABLE IF NOT EXISTS irrigation_decisions' in migration
    assert 'CREATE TABLE IF NOT EXISTS irrigation_commands' in migration
    assert 'CREATE TABLE IF NOT EXISTS audit_logs' in migration
    assert "create_hypertable('sensor_telemetry'" in migration
    assert "create_hypertable('predictions'" in migration


def test_seed_script_uses_metadata_sources():
    seed_script = (PROJECT_ROOT / 'scripts' / 'seed_zones.py').read_text(encoding='utf-8')
    assert 'zone_registry.csv' in seed_script
    assert 'zones.geojson' in seed_script
    assert 'INSERT INTO zones' in seed_script
    assert 'ON CONFLICT (zone_id) DO UPDATE' in seed_script
