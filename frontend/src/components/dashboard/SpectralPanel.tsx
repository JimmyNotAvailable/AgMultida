import { useMemo } from 'react'
import type { NdviHistoryPoint, SpectralResponse, SpectralScene } from '../../lib/api/types'

interface SpectralPanelProps {
  zoneId: string
  spectral: SpectralResponse | null
  isLoading: boolean
  isError: boolean
}

export function SpectralPanel({ zoneId, spectral, isLoading, isError }: SpectralPanelProps) {
  const latestScene = spectral?.scenes[0] ?? null
  const ndviHistory = spectral?.ndvi_history ?? []
  const latestNdvi = ndviHistory.length > 0 ? ndviHistory[ndviHistory.length - 1] : null
  const ndviImageUrl = latestScene?.ndvi_image_url ?? null
  const healthLabel = useNdviHealthLabel(latestNdvi?.mean ?? null)

  if (isLoading) {
    return (
      <article className="field-card spectral-card">
        <div className="field-card-head compact">
          <h3>Quang phổ thực vật</h3>
          <span className="field-badge warn"><span />Đang tải...</span>
        </div>
        <div className="spectral-frame spectral-loading">
          <span>Đang tải ảnh quang phổ...</span>
        </div>
      </article>
    )
  }

  if (isError || !spectral) {
    return (
      <article className="field-card spectral-card">
        <div className="field-card-head compact">
          <h3>Quang phổ thực vật</h3>
          <span className="field-badge danger"><span />Lỗi</span>
        </div>
        <div className="spectral-frame spectral-error">
          <span>Không thể tải dữ liệu quang phổ</span>
        </div>
      </article>
    )
  }

  return (
    <article className="field-card spectral-card">
      <div className="field-card-head compact">
        <h3>Quang phổ thực vật</h3>
        <span className={`field-badge ${healthLabel.badgeClass}`}><span />{healthLabel.label}</span>
      </div>
      <div className="spectral-frame" data-testid="spectral-frame">
        {ndviImageUrl ? (
          <img
            className="spectral-image"
            src={ndviImageUrl}
            alt={`NDVI quang phổ ${zoneId}`}
            loading="lazy"
          />
        ) : (
          <div className="spectral-placeholder">
            <span>Không có ảnh quang phổ</span>
          </div>
        )}
        <div className="spectral-overlay">
          <span className="spectral-label">NDVI — {latestScene?.satellite ?? 'N/A'}</span>
          {latestScene ? (
            <span className="spectral-meta">
              {formatUnixDate(latestScene.dt)} | Mây {latestScene.cloud_cover.toFixed(0)}%
            </span>
          ) : null}
        </div>
      </div>
      <div className="spectral-stats">
        <SpectralStat label="NDVI TB" value={latestNdvi?.mean != null ? latestNdvi.mean.toFixed(3) : 'n/a'} />
        <SpectralStat label="NDVI Max" value={latestNdvi?.max != null ? latestNdvi.max.toFixed(3) : 'n/a'} />
        <SpectralStat label="NDVI Min" value={latestNdvi?.min != null ? latestNdvi.min.toFixed(3) : 'n/a'} />
        <SpectralStat label="Cảnh ảnh" value={`${spectral.scenes.length}`} />
      </div>
      {ndviHistory.length > 1 ? <NdviSparkline history={ndviHistory} /> : null}
    </article>
  )
}

function SpectralStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="spectral-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function NdviSparkline({ history }: { history: NdviHistoryPoint[] }) {
  const { pathD, minLabel, maxLabel } = useMemo(() => {
    const values = history.map((h) => h.mean)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1

    const width = 240
    const height = 40
    const padding = 2

    const points = values.map((v, i) => {
      const x = padding + (i / (values.length - 1)) * (width - padding * 2)
      const y = height - padding - ((v - min) / range) * (height - padding * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })

    return {
      pathD: `M${points.join(' L')}`,
      minLabel: min.toFixed(2),
      maxLabel: max.toFixed(2),
    }
  }, [history])

  return (
    <div className="ndvi-sparkline">
      <span className="sparkline-label">NDVI 90 ngày</span>
      <div className="sparkline-wrap">
        <span className="sparkline-bound">{maxLabel}</span>
        <svg viewBox="0 0 240 40" preserveAspectRatio="none">
          <path d={pathD} fill="none" stroke="var(--field-electric, #2545ff)" strokeWidth="2" />
        </svg>
        <span className="sparkline-bound">{minLabel}</span>
      </div>
    </div>
  )
}

function useNdviHealthLabel(mean: number | null): { label: string; badgeClass: string } {
  if (mean === null) return { label: 'N/A', badgeClass: 'warn' }
  if (mean >= 0.6) return { label: 'Khỏe mạnh', badgeClass: 'good' }
  if (mean >= 0.4) return { label: 'Trung bình', badgeClass: 'warn' }
  return { label: 'Stress cao', badgeClass: 'danger' }
}

function formatUnixDate(dt: number): string {
  return new Date(dt * 1000).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
