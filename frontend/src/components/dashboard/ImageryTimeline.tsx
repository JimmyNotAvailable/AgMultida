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
    return <p className="section-copy" data-testid="imagery-timeline-loading">Loading imagery history...</p>
  }

  if (isError) {
    return <p className="section-copy" data-testid="imagery-timeline-error">Imagery history unavailable.</p>
  }

  if (!scenes.length) {
    return <p className="section-copy">No imagery history yet.</p>
  }

  return (
    <div className="imagery-timeline" aria-label="Imagery timeline" data-testid="imagery-timeline">
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
            {previewUrl ? <img src={previewUrl} alt={`Scene ${index + 1}`} loading="lazy" /> : <span className="timeline-empty" />}
            <strong>{scene.acquisition_time ? new Date(scene.acquisition_time).toLocaleDateString() : `Scene ${index + 1}`}</strong>
            {scene.stale ? <span className="timeline-stale">Stale</span> : null}
          </button>
        )
      })}
    </div>
  )
}
