import type { PredictResponse } from '../../../lib/api/types'
import { isDemoPrediction } from '../hooks/usePredictionFlow'

interface DegradationBannerProps {
  prediction: PredictResponse | null
}

export function DegradationBanner({ prediction }: DegradationBannerProps) {
  if (!prediction) return null
  if (isDemoPrediction(prediction)) {
    return <article className="data-card degraded-banner-card"><strong>Demo prediction. Backend unavailable.</strong></article>
  }
  if (prediction.degraded_mode) {
    return <article className="data-card degraded-banner-card"><strong>Prediction degraded. Low-confidence fallback active.</strong></article>
  }
  return null
}
