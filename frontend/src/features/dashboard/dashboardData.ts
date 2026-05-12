import type { IrrigationDecision, PredictResponse, ZoneStatusResponse } from '../../lib/api/types'

export type ZoneState = 'healthy' | 'moderate' | 'critical'

export interface ZoneBounds {
  min_lng: number
  min_lat: number
  max_lng: number
  max_lat: number
}

export interface ZoneData {
  id: string
  label: string
  name: string
  province: string
  crop: string
  stress: number
  moisture: number
  rain: number
  uncertainty: number
  rec: 'no_irrigation' | 'light' | 'moderate' | 'heavy' | 'hold'
  volume: number
  state: ZoneState
  path: string
  note: string
  bounds?: ZoneBounds
  centroid?: [number, number]
}

export interface ZoneMapFeature {
  type: 'Feature'
  properties: {
    zone_id: string
    zone_name?: string
    province?: string
    crop_type?: string
  }
  geometry: {
    type: 'Polygon'
    coordinates: number[][][]
  }
}

export interface ZoneMapCollection {
  type: 'FeatureCollection'
  features: ZoneMapFeature[]
}

export const zones: ZoneData[] = [
  {
    id: 'DT01', label: 'Zone DT01', name: 'Mỹ Thiện', province: 'Đồng Tháp', crop: 'Rice',
    stress: 0.35, moisture: 32, rain: 0.22, uncertainty: 0.20, rec: 'light', volume: 6,
    state: 'healthy',
    path: 'M0 128 C80 118 120 116 180 106 S290 82 360 96 S470 137 540 118 S680 72 760 88 S840 110 900 86',
    note: 'Khu vực giám sát thực địa',
    bounds: { min_lng: 105.921679, min_lat: 10.438994, max_lng: 105.929597, max_lat: 10.454166 },
    centroid: [105.925638, 10.446580],
  },
  {
    id: 'TN01', label: 'Zone TN01', name: 'Mộc Hoá', province: 'Tây Ninh', crop: 'Rice',
    stress: 0.48, moisture: 25, rain: 0.16, uncertainty: 0.26, rec: 'moderate', volume: 14,
    state: 'moderate',
    path: 'M0 118 C90 104 128 122 202 96 S320 74 404 84 S540 132 602 106 S730 82 900 66',
    note: 'Khu vực giám sát thực địa',
    bounds: { min_lng: 106.012877, min_lat: 10.710084, max_lng: 106.029082, max_lat: 10.725379 },
    centroid: [106.020279, 10.717732],
  },
]

export const zoneMap: ZoneMapCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { zone_id: 'DT01', zone_name: 'Mỹ Thiện', province: 'Đồng Tháp', crop_type: 'Rice' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [105.921894, 10.454166],
          [105.929597, 10.453069],
          [105.928803, 10.438994],
          [105.921679, 10.444522],
          [105.921894, 10.454166],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: { zone_id: 'TN01', zone_name: 'Mộc Hoá', province: 'Tây Ninh', crop_type: 'Rice' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [106.012877, 10.721116],
          [106.019098, 10.725379],
          [106.029082, 10.714467],
          [106.019159, 10.710084],
          [106.012877, 10.721116],
        ]],
      },
    },
  ],
}

export function getZoneById(zoneId: string): ZoneData {
  return zones.find((zone) => zone.id === zoneId) ?? zones[0]
}

export function buildFallbackPrediction(zone: ZoneData): PredictResponse {
  return {
    trace_id: `demo-${zone.id}-predict`,
    zone_id: zone.id,
    timestamp: new Date().toISOString(),
    stress_prob: zone.stress,
    uncertainty: zone.uncertainty,
    confidence_flag: zone.uncertainty > 0.3 ? 'low' : zone.uncertainty > 0.22 ? 'medium' : 'high',
    degraded_mode: zone.uncertainty > 0.38,
    attention_weights: [0.42, 0.33, 0.25],
    model_version: 'local-demo',
    explanation: [
      { feature: 'soil_moisture', weight: 0.42, trend: 'decreasing' },
      { feature: 'rain_forecast_3h', weight: 0.33, trend: 'stable' },
      { feature: 'weather_context', weight: 0.25, trend: 'increasing' },
    ],
    latency_ms: 420,
  }
}

export function buildFallbackDecision(zone: ZoneData, prediction = buildFallbackPrediction(zone)): IrrigationDecision {
  return {
    trace_id: `demo-${zone.id}-recommend`,
    action: zone.rec,
    volume_mm: zone.volume,
    require_ack: prediction.uncertainty > 0.3 || zone.rec === 'heavy',
    reason: zone.rec === 'heavy'
      ? 'critical_stress_low_moisture'
      : zone.rec === 'moderate'
        ? 'moderate_stress'
        : zone.rec === 'hold'
          ? 'rain_override'
          : zone.rec === 'light'
            ? 'early_watch'
            : 'healthy_range',
    safety_override: prediction.degraded_mode,
    degraded_mode: prediction.degraded_mode,
    confidence_flag: prediction.confidence_flag,
    explanation: prediction.explanation,
  }
}

export function buildFallbackStatus(zone: ZoneData): ZoneStatusResponse {
  const prediction = buildFallbackPrediction(zone)
  return {
    trace_id: `demo-${zone.id}-status`,
    zone_id: zone.id,
    latest_prediction: prediction,
    latest_decision: buildFallbackDecision(zone, prediction),
    latest_telemetry: {
      soil_moisture: zone.moisture,
      air_temp: 31,
      ec: 1.2,
      rain_3h: zone.rain,
      rain_forecast_3h: zone.rain,
      source: 'local-demo',
    },
    alerts: zone.state === 'critical'
      ? [{
        alert_id: `demo-${zone.id}-critical`,
        zone_id: zone.id,
        rule_id: 'critical_stress_low_moisture',
        severity: 'critical',
        source: 'alert_engine',
        message: 'High stress with low moisture and weak rain forecast',
        acknowledged: false,
        timestamp: new Date().toISOString(),
      }]
      : [],
    command_state: 'PENDING',
    updated_at: new Date().toISOString(),
  }
}
