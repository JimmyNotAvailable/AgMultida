"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer', 'device')),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS zones (
            zone_id TEXT PRIMARY KEY CHECK (zone_id ~ '^[A-Z][0-9]{2}$'),
            zone_name TEXT NOT NULL,
            country TEXT,
            region TEXT,
            province TEXT,
            crop_type TEXT,
            split TEXT CHECK (split IN ('train', 'val', 'test')),
            synthetic_test_polygon BOOLEAN NOT NULL DEFAULT TRUE,
            purpose TEXT,
            not_field_boundary BOOLEAN NOT NULL DEFAULT TRUE,
            local_timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            geometry_source TEXT,
            notes TEXT,
            geometry JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            device_type TEXT NOT NULL DEFAULT 'sensor',
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'revoked', 'maintenance')),
            api_key_hash TEXT,
            last_seen_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS sensor_telemetry (
            time TIMESTAMPTZ NOT NULL,
            sample_id TEXT NOT NULL,
            device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            soil_moisture DOUBLE PRECISION,
            soil_temp DOUBLE PRECISION,
            air_temp DOUBLE PRECISION,
            humidity DOUBLE PRECISION,
            ec DOUBLE PRECISION,
            ph DOUBLE PRECISION,
            rain_3h DOUBLE PRECISION,
            rain_24h DOUBLE PRECISION,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source_trace JSONB NOT NULL DEFAULT '{}'::jsonb,
            CHECK (
                soil_moisture IS NOT NULL OR soil_temp IS NOT NULL OR air_temp IS NOT NULL OR humidity IS NOT NULL OR
                ec IS NOT NULL OR ph IS NOT NULL OR rain_3h IS NOT NULL OR rain_24h IS NOT NULL
            ),
            CHECK (soil_moisture IS NULL OR (soil_moisture >= 0.0 AND soil_moisture <= 100.0)),
            CHECK (humidity IS NULL OR (humidity >= 0.0 AND humidity <= 100.0)),
            CHECK (rain_3h IS NULL OR rain_3h >= 0.0),
            CHECK (rain_24h IS NULL OR rain_24h >= 0.0),
            CHECK (ph IS NULL OR (ph >= 0.0 AND ph <= 14.0))
        )
        '''
    )
    op.execute("SELECT create_hypertable('sensor_telemetry', 'time', if_not_exists => TRUE)")

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS predictions (
            time TIMESTAMPTZ NOT NULL,
            prediction_id UUID NOT NULL DEFAULT gen_random_uuid(),
            trace_id UUID NOT NULL,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            stress_prob DOUBLE PRECISION NOT NULL CHECK (stress_prob >= 0.0 AND stress_prob <= 1.0),
            uncertainty DOUBLE PRECISION NOT NULL CHECK (uncertainty >= 0.0 AND uncertainty <= 1.0),
            confidence_flag TEXT NOT NULL CHECK (confidence_flag IN ('high', 'medium', 'low')),
            degraded_mode BOOLEAN NOT NULL,
            attention_weights JSONB NOT NULL DEFAULT '[]'::jsonb,
            model_version TEXT NOT NULL,
            explanation JSONB NOT NULL DEFAULT '[]'::jsonb,
            latency_ms DOUBLE PRECISION NOT NULL CHECK (latency_ms >= 0.0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )
    op.execute("SELECT create_hypertable('predictions', 'time', if_not_exists => TRUE)")

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS irrigation_decisions (
            decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trace_id UUID NOT NULL,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            prediction_time TIMESTAMPTZ,
            prediction_trace_id UUID,
            action TEXT NOT NULL CHECK (action IN ('no_irrigation', 'light', 'moderate', 'heavy', 'hold')),
            volume_mm DOUBLE PRECISION NOT NULL CHECK (volume_mm >= 0.0 AND volume_mm <= 30.0),
            require_ack BOOLEAN NOT NULL,
            reason TEXT NOT NULL,
            safety_override BOOLEAN NOT NULL DEFAULT FALSE,
            degraded_mode BOOLEAN NOT NULL DEFAULT FALSE,
            confidence_flag TEXT NOT NULL CHECK (confidence_flag IN ('high', 'medium', 'low')),
            explanation JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS irrigation_commands (
            command_id TEXT PRIMARY KEY,
            trace_id UUID NOT NULL,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            decision_id UUID REFERENCES irrigation_decisions(decision_id) ON DELETE SET NULL,
            action TEXT NOT NULL CHECK (action IN ('no_irrigation', 'light', 'moderate', 'heavy', 'hold')),
            volume_mm DOUBLE PRECISION NOT NULL CHECK (volume_mm >= 0.0 AND volume_mm <= 30.0),
            source TEXT NOT NULL,
            operator_note TEXT,
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'SENT', 'ACKNOWLEDGED', 'ACTIVE', 'FAILED', 'OVERRIDDEN')),
            requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            sent_at TIMESTAMPTZ,
            acknowledged_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            failure_reason TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        '''
    )

    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trace_id UUID,
            actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            actor_device_id TEXT REFERENCES devices(device_id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            zone_id TEXT REFERENCES zones(zone_id) ON DELETE SET NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )

    op.execute('CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_zone_time ON sensor_telemetry (zone_id, time DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_device_time ON sensor_telemetry (device_id, time DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_predictions_zone_time ON predictions (zone_id, time DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_predictions_model_time ON predictions (model_version, time DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_irrigation_decisions_zone_created_at ON irrigation_decisions (zone_id, created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_irrigation_commands_zone_requested_at ON irrigation_commands (zone_id, requested_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_irrigation_commands_status_requested_at ON irrigation_commands (status, requested_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_zone_created_at ON audit_logs (zone_id, created_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id)')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS audit_logs')
    op.execute('DROP TABLE IF EXISTS irrigation_commands')
    op.execute('DROP TABLE IF EXISTS irrigation_decisions')
    op.execute('DROP TABLE IF EXISTS predictions')
    op.execute('DROP TABLE IF EXISTS sensor_telemetry')
    op.execute('DROP TABLE IF EXISTS devices')
    op.execute('DROP TABLE IF EXISTS zones')
    op.execute('DROP TABLE IF EXISTS users')
