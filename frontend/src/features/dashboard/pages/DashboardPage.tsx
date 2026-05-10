import { useMutation } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { DataFusionPanel } from '../../../components/dashboard/DataFusionPanel'
import { ImageryTimeline } from '../../../components/dashboard/ImageryTimeline'
import { ZoneImageryPanel } from '../../../components/dashboard/ZoneImageryPanel'
import { ZoneMap } from '../../../components/dashboard/ZoneMap'
import { ZoneOverlay } from '../../../components/dashboard/ZoneOverlay'
import { LanguageToggle } from '../../../components/shared/LanguageToggle'
import { ThemeToggle } from '../../../components/shared/ThemeToggle'
import { createCommandWithAck, isLocalDemoResponse, recommend, recommendFromCache } from '../../../lib/api'
import { ApiError, type ApiErrorBody, type ImageryScene, type IrrigationDecision, type PredictResponse, type ZoneStatusResponse } from '../../../lib/api/types'
import { useLanguage } from '../../../lib/i18n/useLanguage'
import { AlertFeed } from '../components/AlertFeed'
import { DegradationBanner } from '../components/DegradationBanner'
import { buildFallbackPrediction, getZoneById, zones } from '../dashboardData'
import { useDashboardZones } from '../dashboardStore'
import { isZoneStatusStale, useDashboardQueries } from '../hooks/useDashboardQueries'
import { getUncertaintyBadgeColor, usePredictionFlow } from '../hooks/usePredictionFlow'

const DEFAULT_ZONE_ID = 'A01'
const DEFAULT_TIMESTAMP = '2026-05-08T08:42:00Z'

function getInitialZoneId(): string {
  if (typeof window === 'undefined') return DEFAULT_ZONE_ID
  const queryZone = new URLSearchParams(window.location.search).get('zone')
  return queryZone ?? DEFAULT_ZONE_ID
}

export function DashboardPage() {
  const { t } = useLanguage()
  const [selectedZoneId, setSelectedZoneId] = useState(getInitialZoneId)
  const [lastAction, setLastAction] = useState<'idle' | 'predict' | 'recommend' | 'status' | 'confirm'>('idle')
  const [imageryMode, setImageryMode] = useState<'rgb' | 'ndvi'>('rgb')
  const [imageryVisible, setImageryVisible] = useState(true)
  const [selectedImageryScene, setSelectedImageryScene] = useState<ImageryScene | null>(null)
  const zonesQuery = useDashboardZones()
  const dashboardZones = zonesQuery.data ?? zones
  const selectedZone = useMemo(() => dashboardZones.find((zone) => zone.id === selectedZoneId) ?? getZoneById(selectedZoneId), [dashboardZones, selectedZoneId])

  useEffect(() => {
    if (dashboardZones.length > 0 && !dashboardZones.some((zone) => zone.id === selectedZoneId)) {
      setSelectedZoneId(dashboardZones[0].id)
    }
  }, [dashboardZones, selectedZoneId])

  const { statusQuery: zoneStatusQuery, alertsQuery: zoneAlertsQuery, imageryLatestQuery, imageryHistoryQuery } = useDashboardQueries(selectedZoneId)

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

  const isStatusStale = isZoneStatusStale(zoneStatusQuery.data?.updated_at)

  const zoneStatusPrompt = zoneStatusQuery.data?.latest_prediction ? null : 'Run prediction to populate model output.'

  const predictMutation = usePredictionFlow({ zoneId: selectedZoneId, timestamp: DEFAULT_TIMESTAMP })

  useEffect(() => {
    if (predictMutation.isSuccess) {
      void Promise.all([zoneStatusQuery.refetch(), zoneAlertsQuery.refetch()])
    }
  }, [predictMutation.isSuccess, zoneAlertsQuery, zoneStatusQuery])

  useEffect(() => {
    if (predictMutation.status !== 'idle') {
      setLastAction('predict')
    }
  }, [predictMutation.status])

  const recommendMutation = useMutation({
    mutationFn: async () => {
      const prediction = predictMutation.data ?? buildFallbackPrediction(selectedZone)
      try {
        return await recommendFromCache({
          zone_id: selectedZoneId,
          soil_moisture: selectedZone.moisture,
          rain_forecast_3h: selectedZone.rain,
          attention_weights: prediction.attention_weights,
        })
      } catch (error) {
        if (!(error instanceof ApiError)) {
          throw error
        }
        if (error.status !== 409 || error.body?.error_code !== 'PREDICTION_CACHE_MISS') {
          throw error
        }
      }
      return recommend({
        zone_id: selectedZoneId,
        stress_prob: prediction.stress_prob,
        uncertainty: prediction.uncertainty,
        degraded_mode: prediction.degraded_mode,
        soil_moisture: selectedZone.moisture,
        rain_forecast_3h: selectedZone.rain,
        attention_weights: prediction.attention_weights,
      })
    },
    onMutate: () => setLastAction('recommend'),
    onSuccess: async () => {
      await Promise.all([zoneStatusQuery.refetch(), zoneAlertsQuery.refetch()])
    },
  })

  const [ackOverride, setAckOverride] = useState(false)
  const [commandRejection, setCommandRejection] = useState<ApiErrorBody | null>(null)

  const latestRecommendation = recommendMutation.data
    ? recommendMutation.data
    : zoneStatusQuery.data?.latest_decision ?? null
  const canConfirmServerDecision = !isLocalDemoResponse(zoneStatusQuery.data)
    && !isLocalDemoResponse(predictMutation.data)
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
    onSuccess: async () => {
      setAckOverride(false)
      await Promise.all([zoneStatusQuery.refetch(), zoneAlertsQuery.refetch()])
    },
  })

  const currentPrediction = predictMutation.data?.zone_id === selectedZoneId
    ? predictMutation.data
    : zoneStatusQuery.data?.latest_prediction ?? null
  const currentDecision = latestRecommendation
  const currentStatus = zoneStatusQuery.data?.zone_id === selectedZoneId ? zoneStatusQuery.data : null
  const alerts = zoneAlertsQuery.data ?? currentStatus?.alerts ?? []
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

  useEffect(() => {
    if (selectedZoneId !== zoneStatusQuery.data?.zone_id) setLastAction('status')
  }, [selectedZoneId, zoneStatusQuery.data?.zone_id])

  return (
    <div className="app-shell dashboard-shell">
      <header className="topbar">
        <div className="brand">
          <div className="mark">⌁</div>
          <div>
            <strong>{t('Water Stress Command')}</strong>
            <div className="section-copy">AI diagnosis + irrigation action + zone status</div>
          </div>
        </div>
        <div className="top-actions">
          <span className={`status-pill ${selectedZone.uncertainty > 0.3 ? 'warning' : 'ok'}`}>{selectedZone.uncertainty > 0.3 ? t('Degraded') : t('Live')}</span>
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </header>

      <main className="dashboard-layout dashboard-layout-wide">
        <aside className="panel sidebar-panel">
          <div className="status-pill ok">{t('Field Ops')}</div>
          <h2>{t('Zone Tree')}</h2>
          <p className="section-copy">{t('Select a zone on the map, then run prediction or recommendation.')}</p>
          <div className="sidebar-list">
            {dashboardZones.map((zone) => (
              <button key={zone.id} className={`sidebar-button ${zone.id === selectedZoneId ? 'active' : ''}`} type="button" onClick={() => selectZone(zone.id)}>
                <span><strong>{zone.name}</strong><small>{zone.note}</small></span>
                <span className={`status-dot ${zone.state}`} />
              </button>
            ))}
          </div>
          <div className="action-panel">
            <h3>{t('Input')}</h3>
            <div className="action-summary">
              <div><span>{t('Selected zone')}</span><strong>{selectedZone.id}</strong></div>
              <div><span>Crop</span><strong>{selectedZone.crop}</strong></div>
              <div><span>Province</span><strong>{selectedZone.province}</strong></div>
            </div>
            <button className="btn primary" type="button" onClick={() => predictMutation.mutate()} disabled={predictMutation.isPending}>{t('Run prediction')}</button>
            <button className="btn ghost" type="button" onClick={() => recommendMutation.mutate()} disabled={recommendMutation.isPending}>{t('Run recommendation')}</button>
            <button className="btn ghost" type="button" onClick={() => { setLastAction('status'); void zoneStatusQuery.refetch() }}>{t('Load zone status')}</button>
          </div>
        </aside>

        <section className="data-stack main-stack">
          <article className="zone-map">
            <div className="map-header">
              <div>
                <div className="status-pill warning">{t('Field map')}</div>
                <h2>{selectedZone.name}</h2>
                <p className="section-copy">{t('Map geometry is validation data for product testing.')}</p>
              </div>
              <div className="metric-key"><span>{selectedZone.province}</span><span>{selectedZone.crop}</span><span>{selectedZone.label}</span></div>
            </div>
            <div className="toggle-row imagery-toggle-row">
              <span>Satellite layer</span>
              <button className={`btn ${imageryVisible ? 'primary' : 'ghost'}`} type="button" onClick={() => setImageryVisible((value) => !value)}>
                {imageryVisible ? 'Hide imagery' : 'Show imagery'}
              </button>
            </div>
            <ZoneMap
              selectedZoneId={selectedZoneId}
              onSelect={selectZone}
              imagery={activeImagery}
              imageryMode={imageryMode}
              imageryVisible={imageryVisible}
            />
          </article>

          <ZoneImageryPanel
            latest={displayImagery}
            history={imageryHistory}
            mode={imageryMode}
            isLoading={imageryLatestQuery.isLoading || imageryHistoryQuery.isLoading}
            isError={imageryLatestQuery.isError || imageryHistoryQuery.isError}
            onModeChange={setImageryMode}
          />
          <article className="data-card">
            <h2>Imagery timeline</h2>
            <ImageryTimeline
              scenes={imageryHistory?.scenes ?? []}
              selectedSceneId={displayImagery?.scene_id ?? null}
              isLoading={imageryHistoryQuery.isLoading}
              isError={imageryHistoryQuery.isError}
              onSelect={selectImageryScene}
            />
          </article>
          <DataFusionPanel
            moisture={typeof currentStatus?.latest_telemetry?.soil_moisture === 'number' ? currentStatus.latest_telemetry.soil_moisture : null}
            rain3h={typeof currentStatus?.latest_telemetry?.rain_3h === 'number' ? currentStatus.latest_telemetry.rain_3h : null}
            cloudCover={displayImagery?.cloud_cover ?? null}
            source={displayImagery?.source ?? null}
            isStale={isStatusStale}
            lastUpdated={currentStatus?.updated_at ?? null}
            hasPrediction={currentStatus?.latest_prediction != null}
          />
          {zoneStatusPrompt ? <article className="data-card degraded-banner-card"><strong>{zoneStatusPrompt}</strong></article> : null}

          <div className="result-grid">
            <DegradationBanner prediction={currentPrediction} />
            {(isLocalDemoResponse(currentDecision) || isLocalDemoResponse(currentStatus)) && <article className="data-card degraded-banner-card"><strong>{t('Backend unavailable. Showing local demo result.')}</strong></article>}
            <article className="data-card prediction-card">
              <div className="card-head"><h2>{t('Prediction result')}</h2><span className={`badge ${predictionBadgeClass(currentPrediction?.confidence_flag)}`}>{currentPrediction ? `${t('Confidence')}: ${t(currentPrediction.confidence_flag)}` : t('No result yet')}</span></div>
              <p className="caption">{lastAction === 'predict' && predictMutation.isPending ? t('Prediction is running...') : currentPrediction ? t('Prediction completed.') : t('Click an action to see a concrete model output.')}</p>
              {currentPrediction ? <PredictionResult prediction={currentPrediction} t={t} /> : <EmptyResult t={t} />}
            </article>
            <article className="data-card recommendation-card">
              <div className="card-head"><h2>{t('Recommendation result')}</h2><span className={`badge ${decisionBadgeClass(currentDecision?.action)}`}>{currentDecision ? t(currentDecision.action) : t('No result yet')}</span></div>
              <p className="caption">{lastAction === 'recommend' && recommendMutation.isPending ? t('Recommendation is running...') : currentDecision ? t('Recommendation completed.') : t('Click an action to see a concrete model output.')}</p>
              {currentDecision ? <DecisionResult decision={currentDecision} t={t} /> : <EmptyResult t={t} />}
            </article>
            <article className="data-card status-card">
              <div className="card-head"><h2>{t('Zone status result')}</h2><span className="badge healthy">{currentStatus ? t('Zone status loaded.') : t('No result yet')}</span></div>
              <p className="caption">{zoneStatusQuery.isFetching ? t('Zone status is loading...') : t('View model result')}</p>
              {currentStatus ? <StatusResult status={currentStatus} t={t} /> : <EmptyResult t={t} />}
            </article>
          </div>
        </section>

        <aside className="data-stack">
          <ZoneOverlay selectedZoneId={selectedZoneId} status={currentStatus} prediction={currentPrediction} alerts={alerts} onConfirm={() => confirmMutation.mutate()} isConfirming={confirmMutation.isPending} rejection={commandRejection} ackOverride={ackOverride} onAckOverrideChange={setAckOverride} />
          <article className="data-card explanation-card">
            <h2>{t('Alert feed')}</h2>
            <AlertFeed zoneId={selectedZoneId} alerts={alerts} isLoading={zoneAlertsQuery.isLoading} isError={zoneAlertsQuery.isError} onSelectZone={selectZone} />
          </article>
          <article className="data-card explanation-card">
            <h2>{t('Model explanation')}</h2>
            {currentPrediction?.explanation?.length ? <div className="explanation-list">{currentPrediction.explanation.map((item) => <div className="explanation-item" key={`${item.feature}-${item.trend}`}><strong>{item.feature}</strong><span>{item.weight.toFixed(2)} / {item.trend}</span></div>)}</div> : <p className="section-copy">{t('Explanation unavailable')}</p>}
          </article>
        </aside>
      </main>
    </div>
  )
}

function PredictionResult({ prediction, t }: { prediction: PredictResponse; t: (value: string) => string }) {
  const uncertaintyColor = getUncertaintyBadgeColor(prediction.uncertainty)
  return <><div className="stress-value" data-testid="prediction-percent">{Math.round(prediction.stress_prob * 100)}%</div><div className="progress-track"><span style={{ width: `${Math.round(prediction.stress_prob * 100)}%` }} /></div><div className="metric-grid metric-grid-2"><div><span>{t('Stress probability')}</span><strong>{prediction.stress_prob.toFixed(2)}</strong></div><div><span>{t('Uncertainty')}</span><strong><span className={`badge ${uncertaintyColor}`}>{prediction.uncertainty.toFixed(2)}</span></strong></div><div><span>{t('Model version')}</span><strong>{prediction.model_version}</strong></div><div><span>{t('Latency')}</span><strong>{Math.round(prediction.latency_ms)} ms</strong></div><div><span>{t('Degraded mode')}</span><strong>{t(String(prediction.degraded_mode))}</strong></div><div><span>Trace</span><strong>{prediction.trace_id ?? 'n/a'}</strong></div></div></>
}

function DecisionResult({ decision, t }: { decision: IrrigationDecision; t: (value: string) => string }) {
  return <><div className="volume-readout" data-testid="recommendation-volume">{decision.volume_mm} mm</div><div className="metric-grid metric-grid-2"><div><span>{t('Recommended action')}</span><strong>{t(decision.action)}</strong></div><div><span>{t('Requires acknowledgement')}</span><strong>{t(String(decision.require_ack))}</strong></div><div><span>{t('Reason')}</span><strong>{t(decision.reason)}</strong></div><div><span>{t('Confidence')}</span><strong>{t(decision.confidence_flag)}</strong></div><div><span>{t('Degraded mode')}</span><strong>{t(String(decision.degraded_mode))}</strong></div><div><span>Trace</span><strong>{decision.trace_id ?? 'n/a'}</strong></div></div></>
}

function StatusResult({ status, t }: { status: ZoneStatusResponse; t: (value: string) => string }) {
  return <div className="metric-grid metric-grid-2"><div><span>{t('Selected zone')}</span><strong>{status.zone_id}</strong></div><div><span>{t('Command state')}</span><strong>{status.command_state ?? 'n/a'}</strong></div><div><span>{t('Updated at')}</span><strong>{new Date(status.updated_at).toLocaleString()}</strong></div><div><span>{t('Stress probability')}</span><strong>{status.latest_prediction ? status.latest_prediction.stress_prob.toFixed(2) : 'n/a'}</strong></div><div><span>{t('Recommended action')}</span><strong>{status.latest_decision ? t(status.latest_decision.action) : 'n/a'}</strong></div><div><span>{t('Recommended volume')}</span><strong>{status.latest_decision ? `${status.latest_decision.volume_mm} mm` : 'n/a'}</strong></div></div>
}

function EmptyResult({ t }: { t: (value: string) => string }) {
  return <p className="section-copy">{t('Click an action to see a concrete model output.')}</p>
}

function predictionBadgeClass(confidenceFlag?: PredictResponse['confidence_flag']) {
  if (confidenceFlag === 'low') return 'critical'
  if (confidenceFlag === 'medium') return 'warning'
  return 'healthy'
}

function decisionBadgeClass(action?: IrrigationDecision['action']) {
  if (action === 'heavy') return 'critical'
  if (action === 'moderate' || action === 'light') return 'warning'
  return 'healthy'
}
