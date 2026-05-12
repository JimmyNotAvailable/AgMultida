# PR-09 Summary

## Scope
- Mount backend realtime sync path for `/ws/updates`.
- Add WebSocket manager and Redis subscriber primitives.
- Publish zone-scoped realtime events for prediction/recommendation/alert acknowledgement.
- Add frontend realtime event invalidation helper and dashboard connection status pill.
- Preserve polling fallback when WebSocket is unavailable.

## Changed Files
- `backend/api_gateway/main.py`
- `backend/features/alerts/router.py`
- `backend/features/websocket/__init__.py`
- `backend/features/websocket/manager.py`
- `backend/features/websocket/redis_subscriber.py`
- `backend/features/websocket/router.py`
- `backend/features/websocket/schemas.py`
- `tests/backend/test_websocket_realtime.py`
- `frontend/src/lib/realtime/types.ts`
- `frontend/src/lib/realtime/useWebSocket.ts`
- `frontend/src/lib/realtime/useWebSocket.test.ts`
- `frontend/src/features/dashboard/dashboardStore.ts`
- `frontend/src/features/dashboard/pages/DashboardPage.tsx`

## Validation Results
- Backend expanded tests:
  - `./.venv/Scripts/python.exe -m pytest tests/backend/test_websocket_realtime.py tests/backend/test_alert_lifecycle.py tests/backend/test_alerts_api.py -q`
  - Result: `21 passed`
- Frontend expanded tests:
  - `npm --prefix frontend test -- useWebSocket.test.ts dashboard.test.tsx`
  - Result: `8 passed`

## Constraint Compliance
- Non-blocking runtime: Redis subscriber spawned as `asyncio.Task` in lifespan and cancelled on shutdown.
- Redis Pub/Sub channels supported in subscriber dispatch: `ws:broadcast`, `ws:zone:{zone_id}`, `system:alerts`, `system:health`.
- Event schema enforced via strict Pydantic model: `{event, payload, ts, trace_id}`.
- FE reconnect backoff helper: `1s -> 2s -> 4s -> ... -> 30s cap`.
- FE invalidation helper updates query keys for zone status, alerts, imagery latest/history.
- Polling fallback preserved; no existing query polling removed.
- WS auth remains header-based through existing websocket auth path; no token in URL required by implementation.

## Known Limits
- Redis subscriber currently subscribes shared channels; dynamic per-zone Redis subscription is not yet implemented.
- Backend event publishing currently covers prediction/recommendation/alert acknowledgement; alert_opened/status_changed/imagery_updated publisher hooks are still partial.
- Frontend connection status pill is mounted, but no dedicated visual component file exists yet.
- Existing `/ws/updates` path now supports subscribe messages, but full ping/pong heartbeat is not yet wired into live route traffic.

## Test Note
- PR-09 validation covers manager connect/fanout, subscriber strict parsing, reconnect backoff helper, query invalidation helper, and dashboard regression.
- Full backend suite still has the unrelated known `/v1/commands` rate-limit test issue outside PR-09 scope.
