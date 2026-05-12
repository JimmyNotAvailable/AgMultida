import { useMutation } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DashboardPreviewLayout } from '../components/DashboardPreviewLayout'
import { ThemeToggle } from '../../../components/shared/ThemeToggle'
import { createCommandWithAck, isLocalDemoResponse, recommend, recommendFromCache } from '../../../lib/api'
import { useWebSocket } from '../../../lib/realtime/useWebSocket'
import { ApiError, type ApiErrorBody, type ImageryScene, type IrrigationDecision, type PredictResponse } from '../../../lib/api/types'
import { getZoneById, zones as fallbackZones } from '../dashboardData'
import { connectionStatusLabel, dashboardStore, useDashboardZones } from '../dashboardStore'
import { isZoneStatusStale, useDashboardQueries } from '../hooks/useDashboardQueries'
import { usePredictionFlow } from '../hooks/usePredictionFlow'

const DEFAULT_ZONE_ID = 'A01'
const DEFAULT_TIMESTAMP = '2026-05-08T08:42:00Z'

type ZoneRecommendation = IrrigationDecision & { zone_id: string }

function getInitialZoneId(): string {
  if (typeof window === 'undefined') return DEFAULT_ZONE_ID
  const queryZone = new URLSearchParams(window.location.search).get('zone')
  return queryZone ?? DEFAULT_ZONE_ID
}

export function DashboardPage() {
  const [selectedZoneId, setSelectedZoneId] = useState(getInitialZoneId)
  const [wsStatus, setWsStatus] = useState(dashboardStore.getState().wsStatus)
  const [lastAction, setLastAction] = useState<'idle' | 'predict' | 'recommend' | 'status' | 'confirm'>('idle')
  const [imageryMode, setImageryMode] = useState<'rgb' | 'ndvi'>('rgb')
  const [imageryVisible, setImageryVisible] = useState(true)
  const [selectedImageryScene, setSelectedImageryScene] = useState<ImageryScene | null>(null)
  const zonesQuery = useDashboardZones()
  const dashboardZones = zonesQuery.data?.length ? zonesQuery.data : fallbackZones
  const hasDashboardZones = dashboardZones.length > 0
  const provinceOptions = useMemo(() => [...new Set(dashboardZones.map((zone) => zone.province))], [dashboardZones])
  const selectedZone = useMemo(() => dashboardZones.find((zone) => zone.id === selectedZoneId) ?? getZoneById(selectedZoneId), [dashboardZones, selectedZoneId])

  useEffect(() => {
    if (dashboardZones.length > 0 && !dashboardZones.some((zone) => zone.id === selectedZoneId)) {
      setSelectedZoneId(dashboardZones[0].id)
    }
  }, [dashboardZones, selectedZoneId])

  useWebSocket(selectedZoneId)

  useEffect(() => {
    const timer = window.setInterval(() => setWsStatus(dashboardStore.getState().wsStatus), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const { imageryLatestQuery, imageryHistoryQuery, spectralQuery } = useDashboardQueries(selectedZoneId)

  const currentImagery = imageryLatestQuery.data?.zone_id === selectedZoneId ? imageryLatestQuery.data : null
  const imageryHistory = imageryHistoryQuery.data?.zone_id === selectedZoneId ? imageryHistoryQuery.data : null
  const displayImagery = selectedImageryScene?.zone_id === selectedZoneId ? selectedImageryScene : currentImagery
  const activeImagery = displayImagery && (imageryMode === 'rgb' ? displayImagery.rgb_url : displayImagery.ndvi_url) ? displayImagery : null

  useEffect(() => {
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    url.searchParams.set('zone', selectedZoneId)
    window.history.replaceState({}, '', url)
  }, [selectedZoneId])

  const isStatusStale = isZoneStatusStale(null)

  const predictMutation = usePredictionFlow({ zoneId: selectedZoneId, timestamp: DEFAULT_TIMESTAMP })

  useEffect(() => {
    if (predictMutation.status !== 'idle') {
      setLastAction('predict')
    }
  }, [predictMutation.status])

  const recommendMutation = useMutation<ZoneRecommendation>({
    mutationFn: async () => {
      const prediction = predictMutation.data
      const requestZoneId = selectedZoneId
      const requestZone = selectedZone
      if (!prediction || prediction.zone_id !== requestZoneId) {
        throw new Error('Prediction required before recommendation')
      }
      try {
        const decision = await recommendFromCache({
          zone_id: requestZoneId,
          soil_moisture: requestZone.moisture,
          rain_forecast_3h: requestZone.rain,
          attention_weights: prediction.attention_weights,
        })
        return { ...decision, zone_id: requestZoneId }
      } catch (error) {
        if (!(error instanceof ApiError)) {
          throw error
        }
        if (error.status !== 409 || error.body?.error_code !== 'PREDICTION_CACHE_MISS') {
          throw error
        }
      }
      const decision = await recommend({
        zone_id: requestZoneId,
        stress_prob: prediction.stress_prob,
        uncertainty: prediction.uncertainty,
        degraded_mode: prediction.degraded_mode,
        soil_moisture: requestZone.moisture,
        rain_forecast_3h: requestZone.rain,
        attention_weights: prediction.attention_weights,
      })
      return { ...decision, zone_id: requestZoneId }
    },
    onMutate: () => setLastAction('recommend'),
  })

  const [ackOverride, setAckOverride] = useState(false)
  const [commandRejection, setCommandRejection] = useState<ApiErrorBody | null>(null)

  const latestRecommendation = recommendMutation.data?.zone_id === selectedZoneId ? recommendMutation.data : null
  const canConfirmServerDecision = !isLocalDemoResponse(predictMutation.data)
    && !isLocalDemoResponse(recommendMutation.data)
    && latestRecommendation !== null

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!canConfirmServerDecision || latestRecommendation === null) {
        throw new Error('Trusted server recommendation required before confirm')
      }
      return createCommandWithAck({
        zone_id: selectedZoneId,
        action: latestRecommendation.action,
        volume_mm: latestRecommendation.volume_mm,
        source: 'ai_recommendation',
        operator_note: ackOverride ? 'Operator acknowledged degraded prediction override' : null,
      }, ackOverride)
    },
    onMutate: () => {
      setCommandRejection(null)
      setLastAction('confirm')
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setCommandRejection(error.body)
      }
    },
    onSuccess: () => {
      setAckOverride(false)
    }
  })

  const currentPrediction = predictMutation.data?.zone_id === selectedZoneId ? predictMutation.data : null
  const currentDecision = latestRecommendation
  const currentStatus = null
  const alerts: [] = []
  const resetMutationsRef = useRef({
    predict: predictMutation.reset,
    recommend: recommendMutation.reset,
    confirm: confirmMutation.reset,
  })

  useEffect(() => {
    resetMutationsRef.current = {
      predict: predictMutation.reset,
      recommend: recommendMutation.reset,
      confirm: confirmMutation.reset,
    }
  }, [confirmMutation.reset, predictMutation.reset, recommendMutation.reset])

  const selectZone = useCallback((zoneId: string) => {
    setSelectedZoneId(zoneId)
    resetMutationsRef.current.predict()
    resetMutationsRef.current.recommend()
    resetMutationsRef.current.confirm()
    setLastAction('status')
  }, [])

  useEffect(() => {
    setImageryMode('rgb')
    setImageryVisible(true)
    setSelectedImageryScene(null)
    setAckOverride(false)
    setCommandRejection(null)
  }, [selectedZoneId])

  useEffect(() => {
    if (selectedImageryScene === null && imageryHistory?.scenes.length) {
      setSelectedImageryScene(imageryHistory.scenes[0])
    }
  }, [imageryHistory, selectedImageryScene])

  const selectImageryScene = useCallback((scene: ImageryScene) => {
    setSelectedImageryScene(scene)
  }, [])

  return (
    <div className="field-dashboard-shell">
      <header className="field-topbar"><div className="field-container field-topbar-inner"><div className="field-brand"><span className="field-brand-mark">A</span><span className="field-brand-name">AgMultida</span></div><nav className="field-nav" aria-label="Điều hướng chính"><a href="/">Tổng quan</a><a className="active" href="/dashboard">Bản đồ & Giám sát</a><a href="/reports">Báo cáo</a><a href="/admin">Cài đặt</a></nav><div className="field-actions"><span className={`field-badge ${wsStatus === 'live' ? 'good' : wsStatus === 'reconnecting' ? 'warn' : 'danger'}`}><span />{connectionStatusLabel(wsStatus)}</span><ThemeToggle /></div></div></header>
      <main className="field-container field-main"><section className="field-hero reveal-card"><div className="field-hero-copy"><p className="field-kicker">Giám sát thông minh / Vận hành ổn định</p><h1>Giám sát <em>Nông trường</em></h1><p>Phân tích stress cây trồng, dự báo tưới tiêu và cảnh báo rủi ro dựa trên mô hình ML & dữ liệu cảm biến thời gian thực.</p></div><div className="field-filters"><select aria-label="Tỉnh" value={selectedZone.province} disabled={!hasDashboardZones} onChange={(event) => { const nextZone = dashboardZones.find((zone) => zone.province === event.target.value) ?? selectedZone; selectZone(nextZone.id) }}>{provinceOptions.length > 0 ? provinceOptions.map((province) => <option key={province} value={province}>{province}</option>) : <option>Đang tải vùng</option>}</select><select aria-label="Vùng canh tác" value={selectedZoneId} disabled={!hasDashboardZones} onChange={(event) => selectZone(event.target.value)}>{dashboardZones.map((zone) => <option key={zone.id} value={zone.id}>{zone.label} - {zone.name}</option>)}</select><button className="field-btn primary" type="button" disabled={!hasDashboardZones} onClick={() => setLastAction('status')}>Áp dụng</button></div><div className="field-zone-rail">{dashboardZones.map((zone) => <button key={zone.id} type="button" onClick={() => selectZone(zone.id)}>{zone.name}</button>)}</div></section>
        <DashboardPreviewLayout selectedZoneId={selectedZoneId} selectedZone={selectedZone} zones={dashboardZones} currentStatus={currentStatus} currentPrediction={currentPrediction} currentDecision={currentDecision} alerts={alerts} imageryMode={imageryMode} setImageryMode={setImageryMode} imageryVisible={imageryVisible} setImageryVisible={setImageryVisible} activeImagery={activeImagery} displayImagery={displayImagery} imageryHistory={imageryHistory} imageryLoading={imageryLatestQuery.isLoading || imageryHistoryQuery.isLoading} imageryError={imageryLatestQuery.isError || imageryHistoryQuery.isError} isStatusStale={isStatusStale} spectral={spectralQuery.data ?? null} spectralLoading={spectralQuery.isLoading} spectralError={spectralQuery.isError} zoneAlertsLoading={false} zoneAlertsError={false} selectZone={selectZone} predictMutation={predictMutation} recommendMutation={recommendMutation} confirmMutation={confirmMutation} commandRejection={commandRejection} ackOverride={ackOverride} setAckOverride={setAckOverride} canConfirmServerDecision={canConfirmServerDecision} selectImageryScene={selectImageryScene} /></main>
      <footer className="field-footer"><div className="field-container"><span>Trace ID: <b>{currentPrediction?.trace_id ?? currentDecision?.trace_id ?? 'req_8f9a2b1c'}</b></span><span>Model: <b>{currentPrediction?.model_version ?? 'onnx-v3.1'}</b></span><span>Latency: <b>{currentPrediction ? `${Math.round(currentPrediction.latency_ms)}ms` : '142ms'}</b></span><span>2026 AgMultida</span></div></footer>
    </div>
  )
}
