import { ConfirmAction } from '../../features/dashboard/components/ConfirmAction'
import type { AlertRecord, ApiErrorBody, ZoneStatusResponse } from '../../lib/api/types'
import { getZoneById } from '../../features/dashboard/dashboardData'

interface ZoneOverlayProps {
  selectedZoneId: string
  status: ZoneStatusResponse | null
  prediction?: ZoneStatusResponse['latest_prediction']
  alerts: AlertRecord[]
  onConfirm: () => void
  isConfirming: boolean
  rejection: ApiErrorBody | null
  ackOverride: boolean
  onAckOverrideChange: (value: boolean) => void
}

export function ZoneOverlay({ selectedZoneId, status, prediction: activePrediction, alerts, onConfirm, isConfirming, rejection, ackOverride, onAckOverrideChange }: ZoneOverlayProps) {
  const zone = getZoneById(selectedZoneId)
  const prediction = activePrediction ?? status?.latest_prediction ?? null
  const decision = status?.latest_decision ?? null
  const telemetry = status?.latest_telemetry ?? null
  const soilMoisture = typeof telemetry?.soil_moisture === 'number' ? telemetry.soil_moisture : zone.moisture
  const airTemp = typeof telemetry?.air_temp === 'number' ? telemetry.air_temp : null
  const ec = typeof telemetry?.ec === 'number' ? telemetry.ec : null
  const rain3h = typeof telemetry?.rain_3h === 'number' ? telemetry.rain_3h : zone.rain

  return (
    <aside className="data-card zone-side-panel" aria-label="Zone side panel">
      <div className="card-head">
        <div>
          <h2>{zone.name}</h2>
          <p className="caption">{zone.id} · {zone.province} · {zone.crop}</p>
        </div>
        <span className={`badge ${prediction?.stress_prob && prediction.stress_prob > 0.6 ? 'critical' : prediction?.stress_prob && prediction.stress_prob > 0.4 ? 'warning' : 'healthy'}`}>
          {prediction ? `${Math.round(prediction.stress_prob * 100)}% stress` : 'No status'}
        </span>
      </div>

      <div className="metric-grid metric-grid-2">
        <div><span>Stress prob</span><strong>{prediction ? prediction.stress_prob.toFixed(2) : 'n/a'}</strong></div>
        <div><span>Uncertainty</span><strong>{prediction ? prediction.uncertainty.toFixed(2) : 'n/a'}</strong></div>
        <div><span>Confidence</span><strong>{prediction?.confidence_flag ?? 'n/a'}</strong></div>
        <div><span>Updated</span><strong>{status ? new Date(status.updated_at).toLocaleTimeString() : 'n/a'}</strong></div>
        <div><span>Moisture</span><strong>{soilMoisture}</strong></div>
        <div><span>Temp</span><strong>{airTemp ?? 'n/a'}</strong></div>
        <div><span>EC</span><strong>{ec ?? 'n/a'}</strong></div>
        <div><span>Rain 3h</span><strong>{rain3h}</strong></div>
      </div>
      {prediction?.explanation?.length ? <div className="alert-list"><h3>XAI features</h3>{prediction.explanation.map((item) => <div className="alert-item" key={`${item.feature}-${item.trend}`}><strong>{item.feature}</strong><span>{item.weight.toFixed(2)} · {item.trend}</span></div>)}</div> : null}

      <div className="action-panel">
        <h3>Recommendation</h3>
        <div className="action-summary">
          <div><span>Action</span><strong>{decision?.action ?? 'n/a'}</strong></div>
          <div><span>Volume</span><strong>{decision ? `${decision.volume_mm} mm` : 'n/a'}</strong></div>
          <div><span>Reason</span><strong>{decision?.reason ?? 'n/a'}</strong></div>
        </div>
        <ConfirmAction
          prediction={prediction}
          isConfirming={isConfirming}
          rejection={rejection}
          ackOverride={ackOverride}
          onAckOverrideChange={onAckOverrideChange}
          onConfirm={onConfirm}
        />
      </div>

      <div className="alert-list">
        <h3>Alert Feed</h3>
        {alerts.length ? alerts.map((alert) => (
          <div className="alert-item" key={alert.alert_id}>
            <strong>{alert.severity.toUpperCase()}</strong>
            <span>{alert.message}</span>
          </div>
        )) : <p className="section-copy">No active alerts.</p>}
      </div>
    </aside>
  )
}
