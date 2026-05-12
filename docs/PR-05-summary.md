## PR-05 Markdown Audit Summary

### Scope
PR-05 implements a cache-driven recommendation pipeline on top of PR-04’s prediction trust boundary:
- recommendation creation from latest cached prediction
- decision caching with Redis hot path + memory fallback
- additive `POST /v1/recommend/from-cache`
- dashboard fallback from cache-driven recommendation to payload-driven recommendation only on `PREDICTION_CACHE_MISS`
- zone status reuse of latest cached decision

### Files changed
- `backend/features/recommendation/service.py`
- `backend/features/recommendation/policy.py`
- `backend/features/recommendation/router.py`
- `backend/api_gateway/main.py`
- `backend/core/schemas.py`
- `backend/core/errors.py`
- `frontend/src/lib/api/index.ts`
- `frontend/src/lib/api/types.ts`
- `frontend/src/features/dashboard/pages/DashboardPage.tsx`
- `tests/backend/test_integration_wiring.py`

### Behavior delivered
- `RecommendationService`
  - loads `pred:{zone_id}:latest`
  - evaluates via existing decision engine rule logic
  - stores `decision:{zone_id}:latest` with TTL 10m
  - tolerates Redis outage via memory fallback
- API
  - preserves `POST /v1/recommend`
  - adds `POST /v1/recommend/from-cache`
  - returns `409 PREDICTION_CACHE_MISS` on cached-prediction miss
- Policy
  - `rain_forecast_3h > 15mm` → `no_irrigation`
  - `uncertainty > 0.30` → `HOLD + require_ack`
  - `degraded_mode` → conservative volume reduction
- Audit
  - emits `recommendation_created`
- FE
  - tries cache-driven recommendation first
  - falls back to live payload-driven recommendation only on `PREDICTION_CACHE_MISS`
  - status surface reuses cached latest decision

### Validation results
- Backend
  - `python -m pytest tests/backend/test_integration_wiring.py tests/backend/test_prediction_cache.py tests/backend/test_ai_client.py tests/backend/test_config_guardrails.py`
  - result: **39 passed**
- Frontend tests
  - `npm --prefix frontend test -- --run src/features/dashboard/dashboard.test.tsx src/features/dashboard/hooks/usePredictionFlow.test.ts`
  - result: **6 passed**
- Frontend build
  - `npm --prefix frontend run build`
  - result: **pass**
  - note: existing large MapLibre chunk warning only
- Review
  - final code review: **no HIGH/CRITICAL blockers**
  - final security review: **no HIGH/CRITICAL blockers**

### Constraint compliance checklist
- [x] `NO_RETRAIN`
- [x] `STRANGLER_PATTERN`
- [x] `STORAGE_STRATEGY` — Redis hot path + memory fallback
- [x] `API_CONTRACT` — additive API only, zero breaking changes
- [x] `LOGGING_AUDIT`
- [x] zero DB migration

### Backward-compatibility verification
- `POST /v1/recommend` contract preserved
- stub-mode recommendation behavior preserved
- FE existing dashboard action flow still builds + tests pass
- status endpoint remains backward-compatible while enriched with cached decision reuse

### Known limitations
- `from-cache` requires telemetry-like inputs (`soil_moisture`, `rain_forecast_3h`) for best rule fidelity; schema keeps them optional with safe defaults, and FE supplies them explicitly
- no durable decision-history persistence yet; latest-only cache semantics by design
- no recommendation/command consistency enforcement; intentionally deferred beyond PR-05 scope
