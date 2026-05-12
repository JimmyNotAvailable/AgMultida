"""add zone imagery metadata

Revision ID: 0002_add_zone_imagery_table
Revises: 0001_initial_schema
Create Date: 2026-05-09
"""
from __future__ import annotations

from alembic import op

revision = '0002_add_zone_imagery_table'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS zone_imagery (
            scene_id TEXT PRIMARY KEY,
            zone_id TEXT NOT NULL REFERENCES zones(zone_id) ON DELETE CASCADE,
            acquisition_time TIMESTAMPTZ NOT NULL,
            cloud_cover DOUBLE PRECISION CHECK (cloud_cover >= 0.0 AND cloud_cover <= 100.0),
            rgb_url TEXT,
            ndvi_url TEXT,
            source TEXT NOT NULL DEFAULT 'sentinel-2-l2a',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        '''
    )
    op.execute('CREATE INDEX IF NOT EXISTS idx_zone_imagery_zone_acquired ON zone_imagery (zone_id, acquisition_time DESC)')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS zone_imagery')
