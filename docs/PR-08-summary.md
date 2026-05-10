# PR-08 Summary

## Scope
- Add Telegram alert worker for Redis Stream alert events.
- Consume `alerts:events` with consumer group `alert-monitor`.
- Send Telegram notifications only for open, unsent, moderate/critical alerts.
- Persist Telegram delivery state on the alert hash payload.
- Route permanent send failures to `alerts:dlq`.
- Add Telegram readiness config guard to `/v1/readyz`.
- Surface Telegram env config in `.env.example` and `docker-compose.yml`.

## Changed Files
- `backend/features/alerts/telegram_worker.py`
- `backend/api_gateway/main.py`
- `backend/core/config.py`
- `tests/backend/test_telegram_worker.py`
- `.env.example`
- `docker-compose.yml`

## Validation Results
- PR-08 focused tests:
  - `./.venv/Scripts/python.exe -m pytest tests/backend/test_telegram_worker.py -q`
  - Result: `5 passed`
- PR-08 + readiness regression tests:
  - `./.venv/Scripts/python.exe -m pytest tests/backend/test_telegram_worker.py tests/backend/test_ai_client.py -q`
  - Result: `18 passed`
- Expanded backend alert/gateway tests:
  - `./.venv/Scripts/python.exe -m pytest tests/backend/test_telegram_worker.py tests/backend/test_ai_client.py tests/backend/test_alert_lifecycle.py tests/backend/test_alerts_api.py tests/backend/test_integration_wiring.py -q`
  - Result: `53 passed`

## Constraint Compliance
- Background execution: worker supports `run_forever()` and gateway starts it via non-blocking `asyncio.create_task(...)`.
- Redis Stream consumer group: uses `alerts:events` with group `alert-monitor`.
- Push filter: sends only when `severity in {moderate, critical}`, `status=open`, and `telegram_sent=false`.
- Idempotency: `telegram_sent=true` prevents duplicate push after restart/replay.
- Delivery state: success writes `telegram_sent=true` and `telegram_msg_id` into `alert:{id}` payload.
- Retry/DLQ: retries max 3 attempts with exponential backoff and jitter, then writes to `alerts:dlq` with `retry_count` and `last_error`.
- Config guard: if `ALERT_TELEGRAM_ENABLED=true` but token/chat missing, `/v1/readyz` reports Telegram degraded.

## Known Limits
- Worker is currently in-process under API gateway lifecycle, not a dedicated worker container/process.
- Readiness checks configuration and task presence; it does not call Telegram Bot API health endpoints.
- The worker assumes PR-07 alert hash payloads are valid JSON and trust-scoped to backend-produced events.
- DLQ replay tooling is not implemented in PR-08.

## Test Note
- Full backend suite still has one unrelated known failure outside PR-08 scope:
  - `tests/backend/test_admin_security.py::test_admin_rate_limit_trips_on_repeated_command_calls`
  - Observed behavior: first `/v1/commands` returns `409`, so the rate-limit assertion path does not execute.
