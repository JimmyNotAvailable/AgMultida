import { buildFallbackDecision, buildFallbackPrediction, buildFallbackStatus, getZoneById, zoneMap, zones } from '../../features/dashboard/dashboardData'
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

export async function predict(request: PredictRequest): Promise<PredictResponse> {
  try {
    return await apiRequest<PredictResponse>('/v1/predict', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return buildFallbackPrediction(getZoneById(request.zone_id))
    }
    throw error
  }
}

export async function recommend(request: RecommendRequest): Promise<IrrigationDecision> {
  try {
    return await apiRequest<IrrigationDecision>('/v1/recommend', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return buildFallbackDecision(getZoneById(request.zone_id))
    }
    throw error
  }
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

export async function getZones(): Promise<ZoneRegistryResponse> {
  try {
    return await apiRequest<ZoneRegistryResponse>('/v1/zones')
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return {
        trace_id: 'demo-zones',
        zones: zones.map((zone) => ({
          zone: {
            zone_id: zone.id,
            zone_name: zone.name,
            province: zone.province,
            crop_type: zone.crop,
            split: 'validation',
            local_timezone: 'Asia/Ho_Chi_Minh',
          },
          bounds: {
            min_lng: 105.05,
            min_lat: 10.05,
            max_lng: 105.11,
            max_lat: 10.11,
          },
          centroid: [105.08, 10.08],
        })),
      }
    }
    throw error
  }
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

export async function getZoneStatus(zoneId: string): Promise<ZoneStatusResponse> {
  try {
    return await apiRequest<ZoneStatusResponse>(`/v1/zones/${encodeURIComponent(zoneId)}/status`)
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return buildFallbackStatus(getZoneById(zoneId))
    }
    throw error
  }
}

export async function getZoneAlerts(zoneId: string): Promise<ZoneAlertFeedResponse> {
  try {
    return await apiRequest<ZoneAlertFeedResponse>(`/v1/zones/${encodeURIComponent(zoneId)}/alerts`)
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      const fallback = buildFallbackStatus(getZoneById(zoneId))
      return {
        trace_id: fallback.trace_id,
        zone_id: fallback.zone_id,
        alerts: fallback.alerts ?? [],
      }
    }
    throw error
  }
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
    return [105.05, 10.05, 105.11, 10.11]
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

export async function getZoneImageryLatestSafe(zoneId: string): Promise<ImageryScene> {
  try {
    return await getZoneImageryLatest(zoneId)
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return buildFallbackImagery(zoneId)
    }
    throw error
  }
}

export async function getZoneImageryHistorySafe(zoneId: string, limit = 10): Promise<ImagerySceneCollection> {
  try {
    return await getZoneImageryHistory(zoneId, limit)
  } catch (error) {
    if (shouldUseLocalFallback(error)) {
      return {
        trace_id: `demo-${zoneId}-imagery-history`,
        zone_id: zoneId,
        scenes: [buildFallbackImagery(zoneId)],
      }
    }
    throw error
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
