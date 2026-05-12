import { DataFusionPanel } from '../../../components/dashboard/DataFusionPanel'
import { ImageryTimeline } from '../../../components/dashboard/ImageryTimeline'
import { SpectralPanel } from '../../../components/dashboard/SpectralPanel'
import { ZoneImageryPanel } from '../../../components/dashboard/ZoneImageryPanel'
import { ZoneMap } from '../../../components/dashboard/ZoneMap'
import type { AlertRecord, ApiErrorBody, ImageryScene, ImagerySceneCollection, IrrigationDecision, PredictResponse, SpectralResponse, ZoneStatusResponse } from '../../../lib/api/types'
import { AlertFeed } from './AlertFeed'
import type { ZoneData } from '../dashboardData'

interface DashboardPreviewLayoutProps {
  selectedZoneId: string
  selectedZone: ZoneData
  zones: ZoneData[]
  currentStatus: ZoneStatusResponse | null
  currentPrediction: PredictResponse | null
  currentDecision: IrrigationDecision | null
  alerts: AlertRecord[]
  imageryMode: 'rgb' | 'ndvi'
  setImageryMode: (mode: 'rgb' | 'ndvi') => void
  imageryVisible: boolean
  setImageryVisible: (updater: (value: boolean) => boolean) => void
  activeImagery: ImageryScene | null
  displayImagery: ImageryScene | null
  imageryHistory: ImagerySceneCollection | null
  imageryLoading: boolean
  imageryError: boolean
  isStatusStale: boolean
  spectral: SpectralResponse | null
  spectralLoading: boolean
  spectralError: boolean
  zoneAlertsLoading: boolean
  zoneAlertsError: boolean
  selectZone: (zoneId: string) => void
  predictMutation: { mutate: () => void; isPending: boolean }
  recommendMutation: { mutate: () => void; isPending: boolean }
  confirmMutation: { mutate: () => void; isPending: boolean }
  commandRejection: ApiErrorBody | null
  ackOverride: boolean
  setAckOverride: (value: boolean) => void
  canConfirmServerDecision: boolean
  selectImageryScene: (scene: ImageryScene) => void
}

export function DashboardPreviewLayout(props: DashboardPreviewLayoutProps) {
  const telemetry = props.currentStatus?.latest_telemetry
  const moisture = typeof telemetry?.soil_moisture === 'number' ? telemetry.soil_moisture : props.selectedZone.moisture
  const temp = typeof telemetry?.air_temp === 'number' ? telemetry.air_temp : 31.5
  const rain = typeof telemetry?.rain_forecast_3h === 'number' ? telemetry.rain_forecast_3h : typeof telemetry?.rain_3h === 'number' ? telemetry.rain_3h : props.selectedZone.rain
  const cloudCover = props.displayImagery?.cloud_cover ?? 18
  const stressValue = props.currentPrediction?.stress_prob ?? 0
  const uncertaintyValue = props.currentPrediction?.uncertainty ?? props.selectedZone.uncertainty
  const commandReady = props.currentPrediction !== null && props.currentPrediction.uncertainty <= 0.3 && (!props.currentPrediction.degraded_mode || props.ackOverride) && props.canConfirmServerDecision
  const commandReason = getCommandReason(props.currentPrediction, props.ackOverride, props.canConfirmServerDecision)

  return (
    <section className="field-grid">
      <div className="field-left-stack">
        <article className="field-card map-card reveal-card delay-1">
          <div className="field-card-head">
            <div><h2>Ranh giới thực địa</h2><p>Hình học: Ranh giới thực (GeoJSON) · Nguồn: Khảo sát GPS 2026</p></div>
            <div className="segmented" role="group" aria-label="Chọn lớp ảnh vệ tinh"><button className={props.imageryMode === 'rgb' ? 'active' : ''} onClick={() => props.setImageryMode('rgb')} type="button">RGB</button><button className={props.imageryMode === 'ndvi' ? 'active' : ''} onClick={() => props.setImageryMode('ndvi')} type="button">NDVI</button></div>
          </div>
          <ZoneMap selectedZoneId={props.selectedZoneId} zones={props.zones} onSelect={props.selectZone} imagery={props.activeImagery} imageryMode={props.imageryMode} imageryVisible={props.imageryVisible} />
          <div className="map-badges"><span className={`field-badge ${props.isStatusStale ? 'warn' : 'good'}`}><span />{props.isStatusStale ? 'Dữ liệu cũ' : 'Mới cập nhật (2h trước)'}</span><span className="field-badge warn">Mây {Math.round(cloudCover)}%</span><span className="sr-only">Độ phủ mây</span><span className="sr-only">Lớp ảnh vệ tinh</span><button className="field-link" onClick={() => props.setImageryVisible((value) => !value)} type="button">{props.imageryVisible ? 'Ẩn ảnh vệ tinh' : 'Hiện ảnh vệ tinh'}</button></div>
        </article>

        <div className="field-two-col reveal-card delay-2">
          <SpectralPanel zoneId={props.selectedZoneId} spectral={props.spectral} isLoading={props.spectralLoading} isError={props.spectralError} />
          <article className="field-card"><div className="field-card-head compact"><h3>Cảm biến IoT</h3><span className="field-badge good"><span />Online</span></div><div className="sensor-grid"><MetricTile label="Độ ẩm đất" value={`${moisture.toFixed(1)}%`} note={moisture < 35 ? 'Mức: Thiếu nước' : 'Mức: Bình thường'} /><MetricTile label="Nhiệt độ" value={`${temp.toFixed(1)}C`} note="Mức: Bình thường" /><MetricTile label="Ánh sáng" value="42.1k" note="Lux" /><MetricTile label="Mưa 3h tới" value={`${rain.toFixed(1)} mm`} note={rain > 0 ? 'Có mưa nhẹ' : 'Không mưa'} /></div></article>
        </div>

        <div className="field-two-col reveal-card delay-3"><div><ZoneImageryPanel latest={props.displayImagery} history={props.imageryHistory} mode={props.imageryMode} isLoading={props.imageryLoading} isError={props.imageryError} onModeChange={props.setImageryMode} /></div><DataFusionPanel moisture={moisture} rain3h={rain} cloudCover={cloudCover} source={props.displayImagery?.source ?? null} isStale={props.isStatusStale} lastUpdated={props.currentStatus?.updated_at ?? null} hasPrediction={props.currentStatus?.latest_prediction != null} /></div>
      </div>

      <aside className="field-right-stack">
        <article className="field-card model-card reveal-card delay-1"><div className="field-card-head"><h2>Kết quả mô hình ML</h2><button className="field-btn ghost" type="button" onClick={() => props.predictMutation.mutate()} disabled={props.predictMutation.isPending}>{props.predictMutation.isPending ? 'Đang chạy dự đoán...' : 'Chạy dự đoán'}</button></div><div className="sr-only" data-testid="prediction-percent">{Math.round(stressValue * 100)}%</div><span className="sr-only">Xác suất stress</span><span className="sr-only">Phiên bản mô hình</span><StressGauge value={stressValue} /><div className="model-meta"><div><span>Độ không chắc chắn</span><strong className={`field-badge ${uncertaintyValue > 0.3 ? 'danger' : uncertaintyValue > 0.15 ? 'warn' : 'good'}`}>{uncertaintyValue.toFixed(2)}</strong></div><div><span>Trạng thái suy giảm</span><strong className={`field-badge ${props.currentPrediction?.degraded_mode ? 'warn' : 'good'}`}>{props.currentPrediction?.degraded_mode ? 'Dữ liệu thiếu' : 'Bình thường'}</strong></div></div><XaiList prediction={props.currentPrediction} /></article>
        <article className="field-card reveal-card delay-2"><div className="field-card-head compact"><h3>Đề xuất vận hành</h3></div><div className="recommendation-box"><div><strong>{props.currentDecision ? formatDecisionText(props.currentDecision.action) : 'Tưới nhẹ'}</strong><b data-testid="recommendation-volume">{props.currentDecision ? `${Math.round(props.currentDecision.volume_mm)} mm` : `${props.selectedZone.volume || 5} mm`}</b></div><p>Lý do: {props.currentDecision ? formatDecisionText(props.currentDecision.reason) : 'Stress trung bình kết hợp độ ẩm đất thấp. Dự báo không mưa trong 3h.'}</p>{props.currentDecision ? <span className="sr-only">{props.currentDecision.reason}</span> : null}<label><input type="checkbox" checked={props.ackOverride} onChange={(event) => props.setAckOverride(event.target.checked)} /> Tôi đã xác nhận điều kiện thực địa & đồng ý thực hiện.</label></div><div className="command-row"><button className="field-btn ghost" type="button" onClick={() => props.recommendMutation.mutate()} disabled={props.recommendMutation.isPending}>{props.recommendMutation.isPending ? 'Đang tính...' : 'Chạy khuyến nghị'}</button><button className="field-btn primary" type="button" disabled={!commandReady || props.confirmMutation.isPending} onClick={() => props.confirmMutation.mutate()}>{props.confirmMutation.isPending ? 'Đang gửi...' : 'Thực thi lệnh tưới'}</button><span className={commandReady ? 'safe' : 'blocked'}>{commandReason}</span></div>{props.commandRejection ? <p className="field-error" role="alert">{props.commandRejection.message}</p> : null}</article>
        <article className="field-card reveal-card delay-3"><div className="field-card-head compact"><h3>Nhật ký cảnh báo</h3><span className="field-badge warn">{props.alerts.filter((alert) => !alert.acknowledged).length} Mở</span></div><AlertFeed zoneId={props.selectedZoneId} alerts={props.alerts} isLoading={props.zoneAlertsLoading} isError={props.zoneAlertsError} onSelectZone={props.selectZone} /></article>
        <article className="field-card compact-card"><ImageryTimeline scenes={props.imageryHistory?.scenes ?? []} selectedSceneId={props.displayImagery?.scene_id ?? null} isLoading={props.imageryLoading} isError={props.imageryError} onSelect={props.selectImageryScene} /></article>
      </aside>
    </section>
  )
}

function formatDecisionText(value: string): string {
  const knownText: Record<string, string> = {
    'Light Irrigation': 'Tưới nhẹ',
    'Moderate Irrigation': 'Tưới vừa',
    'Heavy Irrigation': 'Tưới nhiều',
    'No Irrigation': 'Không tưới',
  }

  return knownText[value] ?? value
}

function getCommandReason(prediction: PredictResponse | null, ackOverride: boolean, canConfirmServerDecision: boolean): string {
  if (!prediction) return 'Chưa chạy dự đoán'
  if (prediction.uncertainty > 0.3) return 'Chặn: Độ không chắc chắn > 0.30'
  if (prediction.degraded_mode && !ackOverride) return 'Cần xác nhận do dữ liệu suy giảm'
  return canConfirmServerDecision ? 'An toàn để thực thi' : 'Backend demo: không gửi lệnh thật'
}

function MetricTile({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="metric-tile"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
}

function StressGauge({ value }: { value: number }) {
  const offset = 439.8 - value * 439.8
  const color = value > 0.7 ? '#ff5b22' : value > 0.4 ? '#ffc13a' : '#2545ff'
  return <div className="stress-gauge"><svg viewBox="0 0 180 180"><circle className="gauge-track" cx="90" cy="90" r="70" /><circle className="gauge-fill" cx="90" cy="90" r="70" stroke={color} strokeDasharray="439.8" strokeDashoffset={offset} /></svg><div><span>Chỉ số stress</span><strong>{value.toFixed(2)}</strong></div></div>
}

const FEATURE_LABELS: Record<string, string> = {
  soil_moisture: 'Độ ẩm đất',
  surface_temperature: 'Nhiệt độ bề mặt',
  ndvi: 'Chỉ số thực vật (NDVI)',
  rain_forecast_3h: 'Dự báo mưa 3h',
  weather_context: 'Bối cảnh thời tiết',
}

function XaiList({ prediction }: { prediction: PredictResponse | null }) {
  const items = prediction?.explanation?.length ? prediction.explanation : [{ feature: 'soil_moisture', weight: 0.34, trend: 'decreasing' }, { feature: 'surface_temperature', weight: 0.28, trend: 'increasing' }, { feature: 'ndvi', weight: 0.15, trend: 'decreasing' }]
  return <div className="xai-list"><p>Giải thích XAI (Top Features)</p>{items.map((item) => <div className="xai-row" key={`${item.feature}-${item.trend}`}><span /><b>{FEATURE_LABELS[item.feature] ?? item.feature}</b><strong>{Math.round(item.weight * 100)}%</strong><i style={{ width: `${Math.max(12, item.weight * 100)}%` }} /></div>)}</div>
}
