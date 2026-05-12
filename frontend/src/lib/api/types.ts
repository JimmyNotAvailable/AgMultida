export type ConfidenceFlag = 'low' | 'medium' | 'high'
export type RecAction = 'no_irrigation' | 'light' | 'moderate' | 'heavy' | 'hold'
export type CommandStatus = 'PENDING' | 'SENT' | 'ACKNOWLEDGED' | 'ACTIVE' | 'FAILED' | 'OVERRIDDEN'

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
}

export interface ReadinessResponse {
  status: 'ok' | 'degraded' | string
  mode: 'stub' | 'live' | string
  dependencies: Record<string, Record<string, unknown>>
}

export interface PredictRequest {
  zone_id: string
  timestamp: string
  model_version?: string | null
}

export interface FeatureImportance {
  feature: string
  weight: number
  trend: string
}

export interface PredictResponse {
  trace_id?: string
  prediction_id?: string | null
  zone_id: string
  timestamp: string
  stress_prob: number
  uncertainty: number
  confidence_flag: ConfidenceFlag
  degraded_mode: boolean
  attention_weights: number[]
  model_version: string
  explanation?: FeatureImportance[]
  latency_ms: number
}

export interface RecommendRequest {
  zone_id: string
  stress_prob: number
  uncertainty: number
  degraded_mode: boolean
  soil_moisture: number
  rain_forecast_3h: number
  attention_weights?: number[]
}

export interface RecommendFromCacheRequest {
  zone_id: string
  soil_moisture?: number
  rain_forecast_3h?: number
  attention_weights?: number[]
}

export interface IrrigationDecision {
  trace_id?: string
  action: RecAction
  volume_mm: number
  require_ack: boolean
  reason: string
  safety_override?: boolean
  degraded_mode: boolean
  confidence_flag: ConfidenceFlag
  explanation?: FeatureImportance[]
}

export interface IrrigationCommandRequest {
  zone_id: string
  action: RecAction
  volume_mm: number
  source: string
  operator_note?: string | null
}

export interface IrrigationCommandResponse {
  trace_id?: string
  command_id: string
  zone_id: string
  status: CommandStatus
  timestamp: string
}

export type AlertSeverity = 'critical' | 'moderate' | 'watch' | 'warning' | 'info' | 'degraded'

export interface AlertRecord {
  alert_id: string
  zone_id: string
  rule_id: string
  severity: AlertSeverity
  source: string
  message: string
  acknowledged: boolean
  timestamp: string
}

export interface ZoneAlertFeedResponse {
  trace_id?: string
  zone_id: string
  alerts: AlertRecord[]
}

export interface ImageryScene {
  zone_id: string
  scene_id?: string | null
  acquisition_time?: string | null
  cloud_cover?: number | null
  rgb_url?: string | null
  ndvi_url?: string | null
  source: string
  stale: boolean
}

export interface ImagerySceneCollection {
  trace_id?: string
  zone_id: string
  scenes: ImageryScene[]
}

export interface ZoneStatusResponse {
  trace_id?: string
  zone_id: string
  latest_prediction?: PredictResponse | null
  latest_decision?: IrrigationDecision | null
  latest_telemetry?: Record<string, unknown> | null
  weather?: Record<string, unknown> | null
  imagery?: ImageryScene | null
  alerts?: AlertRecord[] | null
  command_state?: CommandStatus | null
  updated_at: string
}

export interface ZoneRegistryEntry {
  zone_id: string
  zone_name: string
  province: string
  crop_type: string
  split: string
  local_timezone: string
}

export interface ZoneBounds {
  min_lng: number
  min_lat: number
  max_lng: number
  max_lat: number
}

export interface ZoneListItem {
  zone: ZoneRegistryEntry
  bounds?: ZoneBounds
  centroid?: [number, number]
  command_state?: string | null
  confidence_flag?: ConfidenceFlag | null
  degraded_mode?: boolean | null
  updated_at?: string
}

export interface ZoneListResponse {
  trace_id?: string
  zones: ZoneListItem[]
}

export interface ZoneRegistryResponse {
  trace_id?: string
  zones: Array<{
    zone: ZoneRegistryEntry
    bounds: ZoneBounds
    centroid: [number, number]
  }>
}

export interface ApiErrorBody {
  error_code?: string
  message?: string
  trace_id?: string
  details?: Record<string, unknown>
}

export class ApiError extends Error {
  readonly status: number
  readonly body: ApiErrorBody | null

  constructor(message: string, status: number, body: ApiErrorBody | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface SpectralScene {
  zone_id: string
  dt: number
  satellite: string
  cloud_cover: number
  data_coverage: number
  ndvi_image_url: string | null
  evi_image_url: string | null
  truecolor_image_url: string | null
  falsecolor_image_url: string | null
  ndvi_tile_url: string | null
  ndvi_stats_url: string | null
}

export interface NdviHistoryPoint {
  dt: number
  source: string
  cloud_cover: number
  mean: number
  median: number
  min: number
  max: number
  std: number
  p25: number
  p75: number
}

export interface SpectralResponse {
  zone_id: string
  polygon_id: string
  scenes: SpectralScene[]
  ndvi_history: NdviHistoryPoint[]
}
