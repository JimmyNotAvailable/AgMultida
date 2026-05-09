from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))

from psycopg import connect

from core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ZONE_REGISTRY_PATH = PROJECT_ROOT / 'metadata' / 'zone_registry.csv'
ZONES_GEOJSON_PATH = PROJECT_ROOT / 'metadata' / 'zones.geojson'


def load_geometry_by_zone() -> dict[str, dict]:
    with ZONES_GEOJSON_PATH.open(encoding='utf-8') as geojson_file:
        payload = json.load(geojson_file)
    return {
        feature['properties']['zone_id']: feature['geometry']
        for feature in payload.get('features', [])
    }


def main() -> None:
    settings = get_settings()
    if not settings.DATABASE_URL:
        raise RuntimeError('DATABASE_URL must be set before seeding zones')

    geometry_by_zone = load_geometry_by_zone()
    with ZONE_REGISTRY_PATH.open(newline='', encoding='utf-8') as registry_file:
        rows = list(csv.DictReader(registry_file))

    with connect(settings.DATABASE_URL, autocommit=False) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    '''
                    INSERT INTO zones (
                        zone_id,
                        zone_name,
                        country,
                        region,
                        province,
                        crop_type,
                        split,
                        synthetic_test_polygon,
                        purpose,
                        not_field_boundary,
                        local_timezone,
                        geometry_source,
                        notes,
                        geometry,
                        updated_at
                    )
                    VALUES (
                        %(zone_id)s,
                        %(zone_name)s,
                        %(country)s,
                        %(region)s,
                        %(province)s,
                        %(crop_type)s,
                        %(split)s,
                        %(synthetic_test_polygon)s,
                        %(purpose)s,
                        %(not_field_boundary)s,
                        %(local_timezone)s,
                        %(geometry_source)s,
                        %(notes)s,
                        %(geometry)s::jsonb,
                        now()
                    )
                    ON CONFLICT (zone_id) DO UPDATE
                    SET zone_name = EXCLUDED.zone_name,
                        country = EXCLUDED.country,
                        region = EXCLUDED.region,
                        province = EXCLUDED.province,
                        crop_type = EXCLUDED.crop_type,
                        split = EXCLUDED.split,
                        synthetic_test_polygon = EXCLUDED.synthetic_test_polygon,
                        purpose = EXCLUDED.purpose,
                        not_field_boundary = EXCLUDED.not_field_boundary,
                        local_timezone = EXCLUDED.local_timezone,
                        geometry_source = EXCLUDED.geometry_source,
                        notes = EXCLUDED.notes,
                        geometry = EXCLUDED.geometry,
                        updated_at = now()
                    ''',
                    {
                        **row,
                        'synthetic_test_polygon': row['synthetic_test_polygon'].lower() == 'true',
                        'not_field_boundary': row['not_field_boundary'].lower() == 'true',
                        'geometry': json.dumps(geometry_by_zone.get(row['zone_id'])),
                    },
                )
        connection.commit()

    print(f'Seeded {len(rows)} zones into database')


if __name__ == '__main__':
    main()
