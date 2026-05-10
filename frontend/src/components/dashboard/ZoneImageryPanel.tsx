import type { ImageryScene, ImagerySceneCollection } from '../../lib/api/types'

import { toAbsoluteApiUrl } from '../../lib/api'

interface ZoneImageryPanelProps {
  latest: ImageryScene | null
  history: ImagerySceneCollection | null
  mode: 'rgb' | 'ndvi'
  isLoading: boolean
  isError: boolean
  onModeChange: (mode: 'rgb' | 'ndvi') => void
}

export function ZoneImageryPanel({ latest, history, mode, isLoading, isError, onModeChange }: ZoneImageryPanelProps) {
  const previewUrl = toAbsoluteApiUrl(mode === 'rgb' ? latest?.rgb_url ?? null : latest?.ndvi_url ?? null)
  const sceneCount = history?.scenes.length ?? 0
  const isCloudy = typeof latest?.cloud_cover === 'number' && latest.cloud_cover > 30
  const statusLabel = isLoading ? 'Loading' : isError ? 'Unavailable' : latest?.stale ? 'Stale' : isCloudy ? 'Cloudy' : 'Fresh'
  const statusClass = isError || latest?.stale ? 'critical' : isCloudy ? 'warning' : 'healthy'

  return (
    <article className="data-card imagery-panel" data-testid="imagery-panel">
      <div className="card-head">
        <h2>Zone imagery</h2>
        <span className={`badge ${statusClass}`} data-testid="imagery-status">{statusLabel}</span>
      </div>
      <div className="toggle-row">
        <button className={`btn ${mode === 'rgb' ? 'primary' : 'ghost'}`} type="button" onClick={() => onModeChange('rgb')}>RGB</button>
        <button className={`btn ${mode === 'ndvi' ? 'primary' : 'ghost'}`} type="button" onClick={() => onModeChange('ndvi')}>NDVI</button>
      </div>
      {isLoading ? <div className="imagery-placeholder" data-testid="imagery-loading">Loading latest imagery...</div> : null}
      {!isLoading && isError ? <div className="imagery-placeholder imagery-error" data-testid="imagery-error">Imagery service unavailable.</div> : null}
      {!isLoading && !isError && previewUrl ? <img className="imagery-preview" src={previewUrl} alt={`Zone imagery ${mode.toUpperCase()}`} data-testid="imagery-preview" /> : null}
      {!isLoading && !isError && !previewUrl ? <p className="section-copy">Placeholder imagery</p> : null}
      {latest?.stale ? <p className="section-copy imagery-stale-copy" data-testid="imagery-stale-copy">Showing last-known-good imagery while upstream refresh is degraded.</p> : null}
      <div className="metric-grid metric-grid-2">
        <div><span>Acquired</span><strong>{latest?.acquisition_time ? new Date(latest.acquisition_time).toLocaleString() : 'n/a'}</strong></div>
        <div><span>Cloud cover</span><strong>{typeof latest?.cloud_cover === 'number' ? `${latest.cloud_cover.toFixed(1)}%` : 'n/a'}</strong></div>
        <div><span>Source</span><strong>{latest?.source ?? 'n/a'}</strong></div>
        <div><span>History</span><strong>{sceneCount} scenes</strong></div>
      </div>
    </article>
  )
}
