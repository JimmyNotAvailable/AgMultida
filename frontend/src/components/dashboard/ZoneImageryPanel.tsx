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
  const statusLabel = isLoading ? 'Đang tải' : isError ? 'Không khả dụng' : latest?.stale ? 'Dữ liệu cũ' : isCloudy ? 'Nhiều mây' : 'Mới cập nhật'
  const statusClass = isError || latest?.stale ? 'critical' : isCloudy ? 'warning' : 'healthy'

  return (
    <article className="data-card imagery-panel" data-testid="imagery-panel">
      <div className="card-head">
        <h2>Ảnh vùng canh tác</h2>
        <span className={`badge ${statusClass}`} data-testid="imagery-status">{statusLabel}</span>
      </div>
      <div className="toggle-row">
        <button className={`btn ${mode === 'rgb' ? 'primary' : 'ghost'}`} type="button" onClick={() => onModeChange('rgb')}>RGB</button>
        <button className={`btn ${mode === 'ndvi' ? 'primary' : 'ghost'}`} type="button" onClick={() => onModeChange('ndvi')}>NDVI</button>
      </div>
      {isLoading ? <div className="imagery-placeholder" data-testid="imagery-loading">Đang tải ảnh mới nhất...</div> : null}
      {!isLoading && isError ? <div className="imagery-placeholder imagery-error" data-testid="imagery-error">Dịch vụ ảnh vệ tinh hiện chưa phản hồi hoặc bạn chưa đăng nhập hợp lệ.</div> : null}
      {!isLoading && !isError && previewUrl ? <img className="imagery-preview" src={previewUrl} alt={`Ảnh vùng ${mode.toUpperCase()}`} data-testid="imagery-preview" /> : null}
      {!isLoading && !isError && !previewUrl ? <p className="section-copy">Chưa có ảnh {mode.toUpperCase()} cho vùng này.</p> : null}
      {latest?.stale ? <p className="section-copy imagery-stale-copy" data-testid="imagery-stale-copy">Đang hiển thị ảnh gần nhất còn dùng được vì nguồn làm mới phía thượng nguồn đang suy giảm.</p> : null}
      <div className="metric-grid metric-grid-2">
        <div><span>Thời điểm chụp</span><strong>{latest?.acquisition_time ? new Date(latest.acquisition_time).toLocaleString('vi-VN') : 'chưa có'}</strong></div>
        <div><span>Độ che phủ mây</span><strong>{typeof latest?.cloud_cover === 'number' ? `${latest.cloud_cover.toFixed(1)}%` : 'chưa có'}</strong></div>
        <div><span>Nguồn dữ liệu</span><strong>{latest?.source ?? 'chưa có'}</strong></div>
        <div><span>Lịch sử</span><strong>{sceneCount} cảnh ảnh</strong></div>
      </div>
    </article>
  )
}
