interface DataFusionPanelProps {
  moisture: number | null
  rain3h: number | null
  cloudCover: number | null
  source: string | null
}

export function DataFusionPanel({ moisture, rain3h, cloudCover, source }: DataFusionPanelProps) {
  return (
    <article className="data-card imagery-fusion-panel">
      <h2>Data fusion</h2>
      <div className="metric-grid metric-grid-2">
        <div><span>Soil moisture</span><strong>{typeof moisture === 'number' ? moisture : 'n/a'}</strong></div>
        <div><span>Rain 3h</span><strong>{typeof rain3h === 'number' ? rain3h : 'n/a'}</strong></div>
        <div><span>Cloud cover</span><strong>{typeof cloudCover === 'number' ? `${cloudCover.toFixed(1)}%` : 'n/a'}</strong></div>
        <div><span>Source</span><strong>{source ?? 'n/a'}</strong></div>
      </div>
    </article>
  )
}
