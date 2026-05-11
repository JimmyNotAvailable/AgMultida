import { zoneMap, zones } from '../../features/dashboard/dashboardData'
import { apiRequest, getApiBaseUrl } from './client'
import { ApiError, type ApiErrorBody } from './types'
import type {
  HealthResponse,
  ImageryScene,
  ImagerySceneCollection,
  IrrigationCommandRequest,
  IrrigationCommandResponse,
  IrrigationDecision,
  PredictRequest,
  PredictResponse,
  ReadinessResponse,
  RecommendFromCacheRequest,
  RecommendRequest,
  SpectralResponse,
  ZoneAlertFeedResponse,
  ZoneListResponse,
  ZoneRegistryResponse,
  ZoneStatusResponse,
} from './types'

export function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/v1/healthz')
}

export function getReadiness(): Promise<ReadinessResponse> {
  return apiRequest<ReadinessResponse>('/v1/readyz')
}

export function predict(request: PredictRequest): Promise<PredictResponse> {
  return apiRequest<PredictResponse>('/v1/predict', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function recommend(request: RecommendRequest): Promise<IrrigationDecision> {
  return apiRequest<IrrigationDecision>('/v1/recommend', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function recommendFromCache(request: RecommendFromCacheRequest): Promise<IrrigationDecision> {
  return apiRequest<IrrigationDecision>('/v1/recommend/from-cache', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function createCommand(request: IrrigationCommandRequest, _context?: unknown): Promise<IrrigationCommandResponse> {
  return createCommandWithAck(request, false)
}

export function createCommandWithAck(request: IrrigationCommandRequest, ack: boolean): Promise<IrrigationCommandResponse> {
  const query = ack ? '?ack=true' : ''
  return apiRequest<IrrigationCommandResponse>(`/v1/commands${query}`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function getZones(): Promise<ZoneRegistryResponse> {
  return apiRequest<ZoneRegistryResponse>('/v1/zones')
}

export async function getZoneRegistry(): Promise<ZoneRegistryResponse> {
  return getZones()
}

export async function getZoneRegistrySafe(): Promise<ZoneRegistryResponse> {
  try {
    return await getZoneRegistry()
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return getZones()
    }
    throw error
  }
}

export async function getZoneList(): Promise<ZoneListResponse> {
  const registry = await getZoneRegistrySafe()
  return {
    trace_id: registry.trace_id,
    zones: registry.zones.map((item, index) => {
      const zone = zones[index % zones.length]
      return {
        zone: item.zone,
        bounds: item.bounds,
        centroid: item.centroid,
        command_state: 'PENDING',
        confidence_flag: zone.uncertainty > 0.3 ? 'low' : zone.uncertainty > 0.22 ? 'medium' : 'high',
        degraded_mode: zone.uncertainty > 0.38,
        updated_at: new Date().toISOString(),
      }
    }),
  }
}

export type ZoneListItem = ZoneListResponse['zones'][number]

export function getZoneStatus(zoneId: string): Promise<ZoneStatusResponse> {
  return apiRequest<ZoneStatusResponse>(`/v1/zones/${encodeURIComponent(zoneId)}/status`)
}

export function getZoneAlerts(zoneId: string): Promise<ZoneAlertFeedResponse> {
  return apiRequest<ZoneAlertFeedResponse>(`/v1/zones/${encodeURIComponent(zoneId)}/alerts`)
}

export function acknowledgeAlert(alertId: string): Promise<ZoneAlertFeedResponse['alerts'][number]> {
  return apiRequest<ZoneAlertFeedResponse['alerts'][number]>(`/v1/alerts/${encodeURIComponent(alertId)}/ack`, {
    method: 'POST',
  })
}


export async function getZoneImageryLatest(zoneId: string): Promise<ImageryScene> {
  return apiRequest<ImageryScene>(`/v1/zones/${encodeURIComponent(zoneId)}/imagery/latest`)
}

export async function getZoneImageryHistory(zoneId: string, limit = 10): Promise<ImagerySceneCollection> {
  return apiRequest<ImagerySceneCollection>(`/v1/zones/${encodeURIComponent(zoneId)}/imagery/history?limit=${limit}`)
}

export function getImageryPreviewUrl(scene: ImageryScene, mode: 'rgb' | 'ndvi'): string | null {
  return mode === 'rgb' ? scene.rgb_url ?? null : scene.ndvi_url ?? null
}

export function getImageryImageCoordinates(zoneId: string): [[number, number], [number, number], [number, number], [number, number]] {
  const [west, south, east, north] = getImageryBounds(zoneId)
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ]
}

export function toAbsoluteApiUrl(path: string | null): string | null {
  if (!path) {
    return null
  }
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }
  return `${getApiBaseUrl()}${path}`
}

export function getImageryOverlayUrl(scene: ImageryScene, mode: 'rgb' | 'ndvi'): string | null {
  return toAbsoluteApiUrl(getImageryPreviewUrl(scene, mode))
}

export function getImageryBounds(zoneId: string): [number, number, number, number] {
  const feature = zoneMap.features.find((item) => item.properties.zone_id === zoneId)
  const coordinates = feature?.geometry.coordinates[0]
  if (!coordinates?.length) {
    return [105.921679, 10.438994, 105.929597, 10.454166]
  }
  const lngs = coordinates.map(([lng]) => lng)
  const lats = coordinates.map(([, lat]) => lat)
  return [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)]
}

export function buildFallbackImagery(zoneId: string): ImageryScene {
  return {
    zone_id: zoneId,
    scene_id: `demo-${zoneId}-scene`,
    acquisition_time: new Date().toISOString(),
    cloud_cover: 12.5,
    rgb_url: 'https://placehold.co/512x512/png?text=RGB',
    ndvi_url: 'https://placehold.co/512x512/png?text=NDVI',
    source: 'local-demo',
    stale: false,
  }
}

export function getZoneImageryLatestSafe(zoneId: string): Promise<ImageryScene> {
  return getZoneImageryLatest(zoneId)
}

export function getZoneImageryHistorySafe(zoneId: string, limit = 10): Promise<ImagerySceneCollection> {
  return getZoneImageryHistory(zoneId, limit)
}

export async function getZoneSpectral(zoneId: string): Promise<SpectralResponse> {
  return apiRequest<SpectralResponse>(`/v1/zones/${encodeURIComponent(zoneId)}/spectral/latest`)
}

export async function getZoneSpectralSafe(zoneId: string): Promise<SpectralResponse | null> {
  try {
    return await getZoneSpectral(zoneId)
  } catch {
    return null
  }
}

export function isFallbackApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function getApiMessage(body: ApiErrorBody | null | undefined): string | null {
  return body?.message ?? null
}

export function isLocalDemoTrace(traceId?: string): boolean {
  return typeof traceId === 'string' && traceId.startsWith('demo-')
}

export function isLocalDemoResponse(value: { trace_id?: string } | null | undefined): boolean {
  return isLocalDemoTrace(value?.trace_id)
}

export function createFallbackMessage(): string {
  return 'Backend unavailable. Showing local demo result.'
}

function shouldUseLocalFallback(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return true
  }
  return error.status >= 500
}
