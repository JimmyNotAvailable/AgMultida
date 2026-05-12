# PR-07 Summary

## Scope
- Implement Redis-backed alert lifecycle for recommendation-driven alerts.
- Expose alert acknowledgement API.
- Replace legacy zone alert feed path with lifecycle-backed feed.
- Add frontend AlertFeed with loading, error, empty, ack, and zone-pan interactions.
- Validate conditional internal API key header behavior for live AI client.

## Changed Files
- `backend/api_gateway/main.py`
- `backend/features/recommendation/service.py`
- `backend/features/alerts/service.py`
- `backend/features/alerts/router.py`
- `tests/backend/test_ai_client.py`
- `tests/backend/test_alert_lifecycle.py`
- `tests/backend/test_alerts_api.py`
- `frontend/src/lib/api/index.ts`
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/types.ts`
- `frontend/src/features/dashboard/components/AlertFeed.tsx`
- `frontend/src/features/dashboard/components/AlertFeed.test.tsx`
- `frontend/src/features/dashboard/pages/DashboardPage.tsx`

## Validation Results
- Backend targeted validation:
  - `./.venv/Scripts/python.exe -m pytest tests/backend/test_ai_client.py tests/backend/test_alert_lifecycle.py tests/backend/test_alerts_api.py tests/backend/test_integration_wiring.py -q`
  - Result: `48 passed`
- Frontend targeted validation:
  - `npm --prefix frontend test -- AlertFeed.test.tsx dashboard.test.tsx`
  - Result: `8 passed`
- Frontend full validation:
  - `npm --prefix frontend test`
  - Result: `24 passed`

## Constraint Compliance
- `STEP2_HEADER`: `LiveAIClient` sends `X-Internal-API-Key` only when configured; absent-path tests added.
- `ZERO_DB`: Redis/memory only; no DB migration.
- `IDEMPOTENCY`: Hourly dedupe key preserved via `zone_id:type:time_bucket` SHA256.
- `TELEGRAM_SCOPE`: No Telegram HTTP calls implemented in PR-07.
- `API_CONTRACT`: `GET /v1/zones/{id}/alerts` returns `200` with `[]` when empty.
- `FE_STATES`: AlertFeed handles loading, error, empty, ack, and zone pan without page reload.

## Known Limits
- Alert dedupe is hourly and type-based, so repeated same-type alerts within the same hour collapse.
- Zone alert feed now reflects lifecycle alerts only, not legacy derived `AlertRepository` alerts.
- Redis open-list cleanup remains lazy; acknowledged alerts are filtered by payload state.

## Test Note
- Full backend suite currently has one unrelated failing test:
  - `tests/backend/test_admin_security.py::test_admin_rate_limit_trips_on_repeated_command_calls`
  - Observed behavior: first `/v1/commands` returns `409`, so rate-limit assertions do not execute.
  - This was not changed as part of PR-07 scope.
