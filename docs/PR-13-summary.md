# PR-13: Backend Feature Refactor

## Goal

Reduce `backend/api_gateway/main.py` from 760 lines to under 150 lines by extracting
all routes, business logic, and infrastructure into proper domain modules. Zero functional changes.

## Result

- `main.py`: **89 lines** (was 760)
- Tests: **174/176** (identical to pre-PR-13 baseline — 2 pre-existing failures unchanged)
- `sys.path.insert` removed from all backend source files
- PYTHONPATH changed from `/app/backend` → `/app` (fully qualified `backend.*` imports throughout)

## New Package Layout

```
backend/
├── infra/                          # Infrastructure (renamed from platform/ to avoid stdlib clash)
│   ├── cache.py                    # TieredCache (was platform_layer/cache.py)
│   ├── security/
│   │   ├── jwt.py                  # JWT decode, require_role, verify_api_key (was core/security.py)
│   │   └── rate_limit.py           # Rate limiter backends + dependency factory (was core/rate_limit.py)
│   └── storage/
│       └── db.py                   # Connection pool + query helpers (was core/db.py)
├── features/
│   ├── health/
│   │   └── router.py               # GET /v1/healthz, GET /v1/readyz
│   ├── imagery/
│   │   ├── router.py               # GET /v1/imagery/preview/{scene_id}
│   │   ├── stac.py                 # STAC search + scene management (was core/imagery.py)
│   │   └── proxy.py                # PNG rendering + preview cache (was core/imagery_proxy.py)
│   ├── prediction/
│   │   └── router.py               # POST /v1/predict, POST /v1/telemetry
│   ├── recommendation/
│   │   └── router.py               # POST /v1/recommend, POST /v1/recommend/from-cache
│   ├── commands/
│   │   └── router.py               # POST /v1/commands (full impl, was stub)
│   ├── websocket/
│   │   ├── router.py               # WS /ws/updates (full impl, was stub)
│   │   ├── auth.py                 # WS auth helpers extracted from main.py
│   │   └── publish.py              # publish_realtime_event extracted from main.py
│   └── zones/
│       ├── router.py               # All /v1/zones/* routes (extended)
│       ├── loader.py               # load_zone_feature, load_zone_registry, get_zone_bbox
│       ├── weather.py              # fetch_weather_for_zone
│       └── status_builder.py       # build_zone_status, build_alerts, extract_rain_3h
└── api_gateway/
    ├── main.py                     # 89 lines: middleware, lifespan call, router mounts
    ├── dependencies.py             # ADMIN_READ/WRITE_DEPENDENCIES, build_prediction_cache_service
    └── lifespan.py                 # wire_application_services, shutdown_application_services
```

## Compat Shims (backward compatibility for all existing consumers)

| File | Content |
|---|---|
| `core/security.py` | `from backend.infra.security.jwt import *` |
| `core/rate_limit.py` | `from backend.infra.security.rate_limit import *` |
| `core/db.py` | `from backend.infra.storage.db import *` |
| `core/imagery.py` | `from backend.features.imagery.stac import *` |
| `core/imagery_proxy.py` | `from backend.features.imagery.proxy import *` |
| `platform_layer/cache.py` | `from backend.infra.cache import *` |

## Import Migration

All imports across `backend/` and `tests/backend/` migrated from bare module paths to
fully qualified `backend.*` paths:

| Old | New |
|---|---|
| `from core.X` | `from backend.core.X` |
| `from api_gateway.X` | `from backend.api_gateway.X` |
| `from features.X` | `from backend.features.X` |
| `from decision_engine.X` | `from backend.decision_engine.X` |
| `from ai_serving.X` | `from backend.ai_serving.X` |
| `from ingestion_service.X` | `from backend.ingestion_service.X` |
| `from platform_layer.X` | `from backend.platform_layer.X` |

External files updated: `migrations/env.py`, `scripts/seed_zones.py`, `ai_system/decision_engine.py`

## Docker Changes

- All Dockerfiles: `PYTHONPATH=/app/backend` → `PYTHONPATH=/app`
- `docker-compose.yml`: uvicorn commands updated to `backend.*.main:app` pattern
- Module paths (e.g., `uvicorn backend.api_gateway.main:app`) updated everywhere

## Files NOT Modified

`core/config.py`, `core/errors.py`, `core/schemas.py`, `core/geospatial.py`,
`core/weather.py`, `core/zone_status_cache.py`, `core/imagery_persistence.py`,
all `ai_serving/` internals, `decision_engine/` model pipeline.

## Pre-existing Test Failures (unchanged)

1. `test_admin_security.py::test_websocket_accepts_valid_token_and_allowed_origin` — WS stub response format mismatch, existed before PR-13
2. `test_admin_security.py::test_admin_rate_limit_trips_on_repeated_command_calls` — in-memory rate limiter state accumulates across test session, existed before PR-13
