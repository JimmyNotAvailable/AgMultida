import type { IrrigationDecision, PredictResponse, ZoneStatusResponse } from '../../lib/api/types'

export type ZoneState = 'healthy' | 'moderate' | 'critical'

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
  { id: 'A01', label: 'Zone A01', name: 'An Giang A01', province: 'An Giang', crop: 'Rice', stress: 0.22, moisture: 39, rain: 0.28, uncertainty: 0.18, rec: 'no_irrigation', volume: 0, state: 'healthy', path: 'M0 128 C80 118 120 116 180 106 S290 82 360 96 S470 137 540 118 S680 72 760 88 S840 110 900 86', note: 'image, sensor, weather aligned' },
  { id: 'A02', label: 'Zone A02', name: 'An Giang A02', province: 'An Giang', crop: 'Rice', stress: 0.46, moisture: 26, rain: 0.18, uncertainty: 0.24, rec: 'light', volume: 8, state: 'moderate', path: 'M0 118 C90 104 128 122 202 96 S320 74 404 84 S540 132 602 106 S730 82 900 66', note: 'weather synced' },
  { id: 'A03', label: 'Zone A03', name: 'An Giang A03', province: 'An Giang', crop: 'Rice', stress: 0.78, moisture: 18, rain: 0.12, uncertainty: 0.34, rec: 'heavy', volume: 28, state: 'critical', path: 'M0 98 C78 106 152 86 218 72 S330 64 412 76 S506 122 594 70 S724 44 900 34', note: 'sensor drift watch' },
  { id: 'D01', label: 'Zone D01', name: 'Dong Thap D01', province: 'Dong Thap', crop: 'Rice', stress: 0.57, moisture: 22, rain: 0.09, uncertainty: 0.41, rec: 'moderate', volume: 18, state: 'moderate', path: 'M0 126 C82 116 144 128 210 100 S350 80 430 96 S558 144 630 96 S750 72 900 58', note: 'image missing' },
  { id: 'E01', label: 'Zone E01', name: 'Can Tho E01', province: 'Can Tho', crop: 'Rice', stress: 0.31, moisture: 33, rain: 0.24, uncertainty: 0.21, rec: 'light', volume: 6, state: 'healthy', path: 'M0 136 C90 128 142 120 214 112 S340 94 418 104 S548 138 624 118 S762 88 900 92', note: 'stable trend' },
  { id: 'F01', label: 'Zone F01', name: 'Kien Giang F01', province: 'Kien Giang', crop: 'Rice', stress: 0.69, moisture: 20, rain: 0.14, uncertainty: 0.29, rec: 'moderate', volume: 22, state: 'critical', path: 'M0 106 C86 98 148 102 216 84 S342 68 420 82 S526 126 610 82 S742 54 900 48', note: 'recovery watch' },
]

export const zoneMap: ZoneMapCollection = {
  type: 'FeatureCollection',
  features: zones.map((zone, index) => {
    const col = index % 3
    const row = Math.floor(index / 3)
    const x = 105.05 + col * 0.08
    const y = 10.05 + row * 0.08
    return {
      type: 'Feature',
      properties: {
        zone_id: zone.id,
        zone_name: zone.name,
        province: zone.province,
        crop_type: zone.crop,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [x, y],
          [x + 0.06, y + 0.01],
          [x + 0.05, y + 0.055],
          [x + 0.01, y + 0.06],
          [x, y],
        ]],
      },
    }
  }),
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
