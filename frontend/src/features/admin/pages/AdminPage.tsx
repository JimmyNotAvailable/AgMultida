import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { LanguageToggle } from '../../../components/shared/LanguageToggle'
import { ThemeToggle } from '../../../components/shared/ThemeToggle'
import { createCommand, getHealth, getReadiness, getZoneStatus, getZones, predict, recommend } from '../../../lib/api'
import { ApiError } from '../../../lib/api/types'
import type {
  IrrigationCommandRequest,
  IrrigationDecision,
  PredictRequest,
  PredictResponse,
  ReadinessResponse,
  RecAction,
  RecommendRequest,
  ZoneListItem,
  ZoneStatusResponse,
} from '../../../lib/api/types'
import { GuardedRoute, hasAdminAccess } from '../../../lib/auth/guard'
import { useLanguage } from '../../../lib/i18n/useLanguage'

const DEFAULT_ZONE_ID = 'A01'
const DEFAULT_PREDICT_TIMESTAMP = '2024-02-14T03:21:00Z'
const DEFAULT_ACTIONS: RecAction[] = ['no_irrigation', 'light', 'moderate', 'heavy', 'hold']

export function AdminPage() {
  const { t } = useLanguage()
  const hasAccess = hasAdminAccess()
  const [zoneIdInput, setZoneIdInput] = useState(DEFAULT_ZONE_ID)
  const [activeZoneId, setActiveZoneId] = useState(DEFAULT_ZONE_ID)
  const [predictForm, setPredictForm] = useState<PredictRequest>({
    zone_id: DEFAULT_ZONE_ID,
    timestamp: DEFAULT_PREDICT_TIMESTAMP,
    model_version: null,
  })
  const [recommendForm, setRecommendForm] = useState<RecommendRequest>({
    zone_id: DEFAULT_ZONE_ID,
    stress_prob: 0.65,
    uncertainty: 0.12,
    degraded_mode: false,
    soil_moisture: 22,
    rain_forecast_3h: 0.1,
    attention_weights: [],
  })
  const [commandForm, setCommandForm] = useState<IrrigationCommandRequest>({
    zone_id: DEFAULT_ZONE_ID,
    action: 'moderate',
    volume_mm: 12,
    source: 'ai_recommendation',
    operator_note: null,
  })

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: hasAccess,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const readinessQuery = useQuery({
    queryKey: ['readiness'],
    queryFn: getReadiness,
    enabled: hasAccess,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const zonesQuery = useQuery({
    queryKey: ['zones'],
    queryFn: getZones,
    enabled: hasAccess,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const zoneStatusQuery = useQuery({
    queryKey: ['zone-status', activeZoneId],
    queryFn: () => getZoneStatus(activeZoneId),
    enabled: hasAccess,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const predictMutation = useMutation({
    mutationFn: predict,
    onSuccess: (result) => {
      setRecommendForm((current) => ({
        ...current,
        zone_id: result.zone_id,
        stress_prob: result.stress_prob,
        uncertainty: result.uncertainty,
        degraded_mode: result.degraded_mode,
        attention_weights: result.attention_weights,
      }))
      setCommandForm((current) => ({
        ...current,
        zone_id: result.zone_id,
      }))
    },
  })

  const recommendMutation = useMutation({
    mutationFn: recommend,
    onSuccess: (result) => {
      setCommandForm((current) => ({
        ...current,
        action: result.action,
        volume_mm: result.volume_mm,
        source: result.require_ack ? 'ai_recommendation' : current.source,
      }))
    },
  })

  const commandMutation = useMutation({
    mutationFn: createCommand,
  })

  const readinessSummary = sanitizeReadiness(readinessQuery.data)
  const zoneStatusSummary = useMemo(() => sanitizeZoneStatus(zoneStatusQuery.data), [zoneStatusQuery.data])

  function selectZone(zoneId: string) {
    setZoneIdInput(zoneId)
    setActiveZoneId(zoneId)
    setPredictForm((current) => ({ ...current, zone_id: zoneId }))
    setRecommendForm((current) => ({ ...current, zone_id: zoneId }))
    setCommandForm((current) => ({ ...current, zone_id: zoneId }))
  }

  return (
    <GuardedRoute
      title="Admin route"
      description="Internal operations surface is hidden unless explicitly enabled for trusted environments."
    >
      <div className="app-shell">
        <header className="topbar">
          <div>
            <strong>{t('Admin')}</strong>
            <div className="section-copy">Gateway operations surface</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>

        <main style={{ padding: 24 }}>
          <section className="admin-grid">
            <article className="admin-card">
              <div className={`status-pill ${healthQuery.data?.status === 'ok' ? 'ok' : 'warning'}`}>{t('Health')}</div>
              <h2>/v1/healthz</h2>
              <pre>{JSON.stringify(renderQueryState(healthQuery.data, healthQuery.isLoading, healthQuery.error), null, 2)}</pre>
            </article>

            <article className="admin-card">
              <div className={`status-pill ${readinessQuery.data?.status === 'ok' ? 'ok' : 'warning'}`}>{t('Readiness')}</div>
              <h2>/v1/readyz</h2>
              <pre data-testid="readiness-panel" role="status" aria-live="polite">{JSON.stringify(renderQueryState(readinessSummary, readinessQuery.isLoading, readinessQuery.error), null, 2)}</pre>
            </article>

            <article className="admin-card" style={{ gridColumn: '1 / -1' }}>
              <h2>{t('Zones')}</h2>
              <ZoneTable
                zones={zonesQuery.data?.zones ?? []}
                activeZoneId={activeZoneId}
                isLoading={zonesQuery.isLoading}
                error={zonesQuery.error}
                onSelect={(zone) => selectZone(zone.zone.zone_id)}
              />
              <form onSubmit={(event) => {
                event.preventDefault()
                selectZone(zoneIdInput.trim().toUpperCase() || DEFAULT_ZONE_ID)
              }} style={{ display: 'flex', gap: 12, marginTop: 16, flexWrap: 'wrap' }}>
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Manual zone fallback</span>
                  <input value={zoneIdInput} onChange={(event) => setZoneIdInput(event.target.value.toUpperCase())} />
                </label>
                <button type="submit">Load Zone Status</button>
              </form>
              <pre data-testid="zone-status-panel" role="status" aria-live="polite">{JSON.stringify(renderQueryState(zoneStatusSummary, zoneStatusQuery.isLoading, zoneStatusQuery.error), null, 2)}</pre>
            </article>

            <article className="admin-card">
              <h2>{t('Predictions')}</h2>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  predictMutation.mutate({
                    ...predictForm,
                    zone_id: predictForm.zone_id.trim().toUpperCase(),
                    model_version: predictForm.model_version?.trim() || null,
                  })
                }}
                style={{ display: 'grid', gap: 12 }}
              >
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Zone ID</span>
                  <input
                    value={predictForm.zone_id}
                    onChange={(event) => setPredictForm((current) => ({ ...current, zone_id: event.target.value.toUpperCase() }))}
                  />
                </label>
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Timestamp</span>
                  <input
                    value={predictForm.timestamp}
                    onChange={(event) => setPredictForm((current) => ({ ...current, timestamp: event.target.value }))}
                  />
                </label>
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Model version</span>
                  <input
                    value={predictForm.model_version ?? ''}
                    onChange={(event) => setPredictForm((current) => ({ ...current, model_version: event.target.value }))}
                  />
                </label>
                <button type="submit" disabled={predictMutation.isPending}>Run Predict</button>
              </form>
              <pre data-testid="predict-panel" role="status" aria-live="polite">{JSON.stringify(renderMutationState(predictMutation.data, predictMutation.isPending, predictMutation.error), null, 2)}</pre>
            </article>

            <article className="admin-card">
              <h2>Recommend</h2>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  recommendMutation.mutate({
                    ...recommendForm,
                    zone_id: recommendForm.zone_id.trim().toUpperCase(),
                  })
                }}
                style={{ display: 'grid', gap: 12 }}
              >
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Zone ID</span>
                  <input
                    value={recommendForm.zone_id}
                    onChange={(event) => setRecommendForm((current) => ({ ...current, zone_id: event.target.value.toUpperCase() }))}
                  />
                </label>
                <NumberField label="Stress probability" value={recommendForm.stress_prob} onChange={(value) => setRecommendForm((current) => ({ ...current, stress_prob: value }))} />
                <NumberField label="Uncertainty" value={recommendForm.uncertainty} onChange={(value) => setRecommendForm((current) => ({ ...current, uncertainty: value }))} />
                <NumberField label="Soil moisture" value={recommendForm.soil_moisture} onChange={(value) => setRecommendForm((current) => ({ ...current, soil_moisture: value }))} />
                <NumberField label="Rain forecast 3h" value={recommendForm.rain_forecast_3h} onChange={(value) => setRecommendForm((current) => ({ ...current, rain_forecast_3h: value }))} />
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={recommendForm.degraded_mode}
                    onChange={(event) => setRecommendForm((current) => ({ ...current, degraded_mode: event.target.checked }))}
                  />
                  <span>Degraded mode</span>
                </label>
                <button type="submit" disabled={recommendMutation.isPending}>Run Recommend</button>
              </form>
              <pre data-testid="recommend-panel" role="status" aria-live="polite">{JSON.stringify(renderMutationState(recommendMutation.data, recommendMutation.isPending, recommendMutation.error), null, 2)}</pre>
            </article>

            <article className="admin-card">
              <h2>Command Runner</h2>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  commandMutation.mutate({
                    ...commandForm,
                    zone_id: commandForm.zone_id.trim().toUpperCase(),
                    operator_note: commandForm.operator_note?.trim() || null,
                  })
                }}
                style={{ display: 'grid', gap: 12 }}
              >
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Zone ID</span>
                  <input
                    value={commandForm.zone_id}
                    onChange={(event) => setCommandForm((current) => ({ ...current, zone_id: event.target.value.toUpperCase() }))}
                  />
                </label>
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Action</span>
                  <select
                    value={commandForm.action}
                    onChange={(event) => setCommandForm((current) => ({ ...current, action: event.target.value as RecAction }))}
                  >
                    {DEFAULT_ACTIONS.map((action) => (
                      <option key={action} value={action}>{action}</option>
                    ))}
                  </select>
                </label>
                <NumberField label="Volume mm" value={commandForm.volume_mm} onChange={(value) => setCommandForm((current) => ({ ...current, volume_mm: value }))} />
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Source</span>
                  <input value={commandForm.source} onChange={(event) => setCommandForm((current) => ({ ...current, source: event.target.value }))} />
                </label>
                <label style={{ display: 'grid', gap: 4 }}>
                  <span>Operator note</span>
                  <input
                    value={commandForm.operator_note ?? ''}
                    onChange={(event) => setCommandForm((current) => ({ ...current, operator_note: event.target.value }))}
                  />
                </label>
                <button type="submit" disabled={commandMutation.isPending}>Send Command</button>
              </form>
              <pre data-testid="command-panel" role="status" aria-live="polite">{JSON.stringify(renderMutationState(commandMutation.data, commandMutation.isPending, commandMutation.error), null, 2)}</pre>
            </article>
          </section>
        </main>
      </div>
    </GuardedRoute>
  )
}

interface ZoneTableProps {
  zones: ZoneListItem[]
  activeZoneId: string
  isLoading: boolean
  error: unknown
  onSelect: (zone: ZoneListItem) => void
}

function ZoneTable({ zones, activeZoneId, isLoading, error, onSelect }: ZoneTableProps) {
  if (isLoading) {
    return <div role="status">Loading zones...</div>
  }

  if (error) {
    return <div role="status">{getErrorMessage(error)}</div>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table data-testid="zone-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">Zone</th>
            <th align="left">Name</th>
            <th align="left">Province</th>
            <th align="left">Crop</th>
            <th align="left">Split</th>
            <th align="left">Status</th>
            <th align="left">Updated</th>
          </tr>
        </thead>
        <tbody>
          {zones.map((zoneItem) => {
            const isActive = zoneItem.zone.zone_id === activeZoneId
            return (
              <tr
                key={zoneItem.zone.zone_id}
                data-testid={`zone-row-${zoneItem.zone.zone_id}`}
                aria-selected={isActive}
                onClick={() => onSelect(zoneItem)}
                style={{ cursor: 'pointer', background: isActive ? 'rgba(59, 130, 246, 0.15)' : 'transparent' }}
              >
                <td>{zoneItem.zone.zone_id}</td>
                <td>{zoneItem.zone.zone_name}</td>
                <td>{zoneItem.zone.province}</td>
                <td>{zoneItem.zone.crop_type}</td>
                <td>{zoneItem.zone.split}</td>
                <td>{zoneItem.command_state ?? zoneItem.confidence_flag ?? 'idle'}</td>
                <td>{zoneItem.updated_at}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface NumberFieldProps {
  label: string
  value: number
  onChange: (value: number) => void
}

function NumberField({ label, value, onChange }: NumberFieldProps) {
  return (
    <label style={{ display: 'grid', gap: 4 }}>
      <span>{label}</span>
      <input
        type="number"
        value={Number.isFinite(value) ? value : ''}
        onChange={(event) => {
          const nextValue = event.target.valueAsNumber
          if (Number.isFinite(nextValue)) {
            onChange(nextValue)
          }
        }}
      />
    </label>
  )
}

function renderQueryState<T>(data: T | undefined, isLoading: boolean, error: unknown): T | { loading: true } | { error: string } {
  if (isLoading) {
    return { loading: true }
  }

  if (error) {
    return { error: getErrorMessage(error) }
  }

  return data ?? { error: 'No data available' }
}

function renderMutationState<T>(data: T | undefined, isPending: boolean, error: unknown): T | { loading: true } | { error: string } | { idle: true } {
  if (isPending) {
    return { loading: true }
  }

  if (error) {
    return { error: getErrorMessage(error) }
  }

  return data ?? { idle: true }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return 'Service unavailable'
  }

  if (error instanceof Error) {
    return 'Service unavailable'
  }

  return 'Unexpected error'
}

function sanitizeReadiness(readiness: ReadinessResponse | undefined) {
  if (!readiness) {
    return undefined
  }

  const dependencies = Object.fromEntries(
    Object.entries(readiness.dependencies ?? {}).map(([name, value]) => {
      const record = value as Record<string, unknown>
      return [
        name,
        {
          status: record.status,
          checked_at: record.checked_at,
          model_loaded: record.model_loaded,
          manifest_loaded: record.manifest_loaded,
          upstream_last_error: record.upstream_last_error ? 'Dependency unavailable' : undefined,
        },
      ]
    }),
  )

  return {
    status: readiness.status,
    mode: readiness.mode,
    dependencies,
  }
}

function sanitizeZoneStatus(zoneStatus: ZoneStatusResponse | undefined) {
  if (!zoneStatus) {
    return undefined
  }

  return {
    trace_id: zoneStatus.trace_id,
    zone_id: zoneStatus.zone_id,
    command_state: zoneStatus.command_state,
    updated_at: zoneStatus.updated_at,
    latest_prediction: zoneStatus.latest_prediction
      ? {
          zone_id: zoneStatus.latest_prediction.zone_id,
          timestamp: zoneStatus.latest_prediction.timestamp,
          stress_prob: zoneStatus.latest_prediction.stress_prob,
          uncertainty: zoneStatus.latest_prediction.uncertainty,
          confidence_flag: zoneStatus.latest_prediction.confidence_flag,
          degraded_mode: zoneStatus.latest_prediction.degraded_mode,
        }
      : null,
    latest_decision: zoneStatus.latest_decision
      ? {
          action: zoneStatus.latest_decision.action,
          volume_mm: zoneStatus.latest_decision.volume_mm,
          require_ack: zoneStatus.latest_decision.require_ack,
          reason: zoneStatus.latest_decision.reason,
          degraded_mode: zoneStatus.latest_decision.degraded_mode,
          confidence_flag: zoneStatus.latest_decision.confidence_flag,
        }
      : null,
    latest_telemetry: zoneStatus.latest_telemetry ? 'Available' : null,
  }
}

export function applyPredictToRecommend(form: RecommendRequest, result: PredictResponse): RecommendRequest {
  return {
    ...form,
    zone_id: result.zone_id,
    stress_prob: result.stress_prob,
    uncertainty: result.uncertainty,
    degraded_mode: result.degraded_mode,
    attention_weights: result.attention_weights,
  }
}

export function applyRecommendationToCommand(form: IrrigationCommandRequest, result: IrrigationDecision): IrrigationCommandRequest {
  return {
    ...form,
    action: result.action,
    volume_mm: result.volume_mm,
    source: result.require_ack ? 'ai_recommendation' : form.source,
  }
}
