import { toAbsoluteApiUrl } from '../../lib/api'
import type { ImageryScene } from '../../lib/api/types'

interface ImageryTimelineProps {
  scenes: ImageryScene[]
  selectedSceneId: string | null
  isLoading: boolean
  isError: boolean
  onSelect: (scene: ImageryScene) => void
}

export function ImageryTimeline({ scenes, selectedSceneId, isLoading, isError, onSelect }: ImageryTimelineProps) {
  if (isLoading) {
    return <p className="section-copy" data-testid="imagery-timeline-loading">Đang tải lịch sử ảnh...</p>
  }

  if (isError) {
    return <p className="section-copy" data-testid="imagery-timeline-error">Không thể tải lịch sử ảnh vệ tinh.</p>
  }

  if (!scenes.length) {
    return <p className="section-copy">Chưa có lịch sử ảnh cho vùng này.</p>
  }

  return (
    <div className="imagery-timeline" aria-label="Lịch sử ảnh vệ tinh" data-testid="imagery-timeline">
      {scenes.slice(0, 10).map((scene, index) => {
        const previewUrl = toAbsoluteApiUrl(scene.rgb_url ?? scene.ndvi_url ?? null)
        return (
          <button
            key={scene.scene_id ?? `${scene.zone_id}-${index}`}
            className={`timeline-scene ${scene.scene_id === selectedSceneId ? 'active' : ''}`}
            type="button"
            onClick={() => onSelect(scene)}
            data-testid="imagery-timeline-scene"
          >
            {previewUrl ? <img src={previewUrl} alt={`Cảnh ảnh ${index + 1}`} loading="lazy" /> : <span className="timeline-empty" />}
            <strong>{scene.acquisition_time ? new Date(scene.acquisition_time).toLocaleDateString('vi-VN') : `Cảnh ảnh ${index + 1}`}</strong>
            {scene.stale ? <span className="timeline-stale">Dữ liệu cũ</span> : null}
          </button>
        )
      })}
    </div>
  )
}
