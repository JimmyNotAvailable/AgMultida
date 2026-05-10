# PR-12 Summary

## Scope
- Comprehensive E2E, fallback validation, and failure-path tests across backend (pytest), frontend (Vitest), and browser (Playwright).
- Zero model accuracy assertions — focus on operational behavior: response shape, cache read/write, uncertainty gates, degraded fallbacks.
- Fix Vitest `toBeDisabled` assertion compatibility (jest-dom matcher unavailable in project setup).

## Changed Files
- `tests/backend/test_command_safety_gate.py` (new, 15 tests)
- `tests/backend/test_recommend_from_cache.py` (new, 7 async tests)
- `tests/backend/test_runtime_guard.py` (new, 12 tests)
- `frontend/src/features/dashboard/components/DegradationBanner.test.tsx` (new, 6 tests)
- `frontend/src/features/dashboard/components/AlertFeed.test.tsx` (enhanced, +5 tests)
- `frontend/src/lib/realtime/useWebSocket.test.ts` (enhanced, +8 tests)
- `frontend/tests/e2e/upgrade_operational_loop.spec.ts` (new, 7 E2E scenarios)

## Validation Results
- **Backend pytest:** 174/176 passed. 2 pre-existing failures in `test_admin_security.py` (rate-limit test hits command safety gate without stored prediction; websocket origin test). Not introduced by PR-12.
- **Frontend Vitest:** 49/49 passed (10 test files).
- **E2E Playwright:** spec authored with golden path + failure path + WS resilience scenarios. Requires running dev server for execution.

## Pre-existing Test Isolation Note
`test_admin_rate_limit_trips_on_repeated_command_calls` and `test_websocket_accepts_valid_token_and_allowed_origin` in `test_admin_security.py` fail due to command safety gate requiring a cached prediction before command dispatch. These failures predate PR-12 and are isolated from all PR-12 changes.

## Key Test Coverage
- **Command safety gate:** no prediction, high uncertainty, boundary 0.30, degraded ack flows, expired prediction, zone mismatch, demo source in production/development.
- **Recommend-from-cache:** cache hit/miss, alert emission, degraded propagation, rain override, uncertainty hold.
- **Runtime guard:** dev auth bypass, production fail-fast (JWT, auth, stubs, WS auth, HSTS), structured error contract, error masking.
- **DegradationBanner:** null/normal/demo/degraded rendering, CSS class mapping.
- **AlertFeed:** severity classes, ack button lifecycle, mutation disable state, multi-alert ordering.
- **WebSocket:** event invalidation per type, reconnect delay, polling fallback, status labels.
- **E2E golden path:** dashboard mount -> zone load -> predict -> recommend -> alert -> UI update, zone selection reset, 503 fallback with demo banner, imagery timeout placeholder, uncertainty gate rejection, no-blank-screen guarantee.
