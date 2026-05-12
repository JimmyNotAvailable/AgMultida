interface DataFusionPanelProps {
  moisture: number | null
  rain3h: number | null
  cloudCover: number | null
  source: string | null
  isStale?: boolean
  lastUpdated?: string | null
  hasPrediction?: boolean
}

export function DataFusionPanel({ moisture, rain3h, cloudCover, source, isStale = false, lastUpdated = null, hasPrediction = true }: DataFusionPanelProps) {
  return (
    <article className="data-card imagery-fusion-panel">
      <h2>Tổng hợp dữ liệu</h2>
      {isStale ? <p className="section-copy">Dữ liệu tổng hợp đã cũ · cập nhật lần cuối {lastUpdated ? new Date(lastUpdated).toLocaleString('vi-VN') : 'chưa có'}</p> : null}
      {!hasPrediction ? <p className="section-copy">Hãy chạy dự đoán để điền kết quả mô hình cho vùng này.</p> : null}
      <div className="metric-grid metric-grid-2">
        <div><span>Độ ẩm đất</span><strong>{typeof moisture === 'number' ? moisture : 'chưa có'}</strong></div>
        <div><span>Mưa 3 giờ tới</span><strong>{typeof rain3h === 'number' ? rain3h : 'chưa có'}</strong></div>
        <div><span>Độ che phủ mây</span><strong>{typeof cloudCover === 'number' ? `${cloudCover.toFixed(1)}%` : 'chưa có'}</strong></div>
        <div><span>Nguồn dữ liệu</span><strong>{source ?? 'chưa có'}</strong></div>
      </div>
    </article>
  )
}
