from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
from pydantic import ValidationError

from backend.core.errors import AgTechError, ErrorCode
from backend.core.schemas import TelemetryIngestRequest, TelemetryIngestResponse


@runtime_checkable
class IngestionClient(Protocol):
    async def ingest(self, req: TelemetryIngestRequest) -> TelemetryIngestResponse: ...

    async def ready(self) -> dict[str, object]: ...


class StubIngestionClient:
    async def ingest(self, req: TelemetryIngestRequest) -> TelemetryIngestResponse:
        return TelemetryIngestResponse(
            accepted=True,
            sample_id=f"{req.zone_id}_{req.timestamp.strftime('%Y%m%d%H%M')}_{req.device_id}",
            timestamp=req.timestamp,
        )

    async def ready(self) -> dict[str, object]:
        return {'status': 'stub'}


class LiveIngestionClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        internal_api_key: str = '',
        header_name: str = 'X-Internal-API-Key',
    ) -> None:
        self._client = http_client
        self._internal_headers = {header_name: internal_api_key} if internal_api_key else {}

    async def ingest(self, req: TelemetryIngestRequest) -> TelemetryIngestResponse:
        try:
            response = await self._client.post(
                '/internal/telemetry',
                json=req.model_dump(mode='json'),
                headers=self._internal_headers or None,
            )
            response.raise_for_status()
            return TelemetryIngestResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise AgTechError(
                error_code=ErrorCode.TELEMETRY_REJECTED,
                message='Ingestion service returned an invalid response',
                status_code=502,
                details={'service': 'ingestion_service', 'reason': 'invalid_response'},
            ) from exc
        except httpx.TimeoutException as exc:
            raise AgTechError(
                error_code=ErrorCode.DEGRADED_SERVICE,
                message='Ingestion service did not respond within timeout',
                status_code=504,
                details={'service': 'ingestion_service'},
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = {}
            try:
                body = exc.response.json()
            except ValueError:
                body = {}
            raise AgTechError(
                error_code=ErrorCode(body.get('error_code', ErrorCode.DEGRADED_SERVICE.value)),
                message=body.get('message', 'Ingestion service returned an error'),
                status_code=exc.response.status_code,
                details=body.get('details', {'service': 'ingestion_service'}),
            ) from exc
        except httpx.HTTPError as exc:
            raise AgTechError(
                error_code=ErrorCode.DEGRADED_SERVICE,
                message='Ingestion service communication failure',
                status_code=502,
                details={'service': 'ingestion_service'},
            ) from exc

    async def ready(self) -> dict[str, object]:
        try:
            response = await self._client.get('/readyz', headers=self._internal_headers or None)
            response.raise_for_status()
            body = response.json()
            return {
                'status': body.get('status', 'degraded'),
                'database': body.get('dependencies', {}).get('database'),
            }
        except httpx.HTTPError:
            return {
                'status': 'degraded',
                'database': None,
            }

    async def close(self) -> None:
        await self._client.aclose()
