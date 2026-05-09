import type { AlertRecord, ZoneStatusResponse } from '../../lib/api/types'
import { getZoneById } from '../../features/dashboard/dashboardData'

interface ZoneOverlayProps {
  selectedZoneId: string
  status: ZoneStatusResponse | null
  alerts: AlertRecord[]
  onConfirm: () => void
  isConfirming: boolean
}

export function ZoneOverlay({ selectedZoneId, status, alerts, onConfirm, isConfirming }: ZoneOverlayProps) {
  const zone = getZoneById(selectedZoneId)
  const prediction = status?.latest_prediction ?? null
  const decision = status?.latest_decision ?? null
  const telemetry = status?.latest_telemetry ?? null
  const soilMoisture = typeof telemetry?.soil_moisture === 'number' ? telemetry.soil_moisture : zone.moisture
  const airTemp = typeof telemetry?.air_temp === 'number' ? telemetry.air_temp : null
  const ec = typeof telemetry?.ec === 'number' ? telemetry.ec : null
  const rain3h = typeof telemetry?.rain_3h === 'number' ? telemetry.rain_3h : zone.rain
  const confirmBlocked = prediction ? prediction.uncertainty > 0.3 : true

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

      <div className="action-panel">
        <h3>Recommendation</h3>
        <div className="action-summary">
          <div><span>Action</span><strong>{decision?.action ?? 'n/a'}</strong></div>
          <div><span>Volume</span><strong>{decision ? `${decision.volume_mm} mm` : 'n/a'}</strong></div>
          <div><span>Reason</span><strong>{decision?.reason ?? 'n/a'}</strong></div>
        </div>
        <button className="btn primary" type="button" disabled={confirmBlocked || isConfirming} onClick={onConfirm}>
          {confirmBlocked ? 'Confirm blocked by uncertainty' : isConfirming ? 'Confirming...' : 'Confirm irrigation'}
        </button>
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
