import { useMutation } from '@tanstack/react-query'
import { predict } from '../../../lib/api'
import type { PredictResponse } from '../../../lib/api/types'

interface UsePredictionFlowArgs {
  zoneId: string
  timestamp: string
}

export function usePredictionFlow({ zoneId, timestamp }: UsePredictionFlowArgs) {
  return useMutation<PredictResponse>({
    mutationFn: () => predict({ zone_id: zoneId, timestamp, model_version: null }),
  })
}

export function getUncertaintyBadgeColor(uncertainty: number): 'green' | 'yellow' | 'red' {
  if (uncertainty < 0.15) return 'green'
  if (uncertainty <= 0.30) return 'yellow'
  return 'red'
}

export function isDemoPrediction(prediction: PredictResponse | null | undefined): boolean {
  return typeof prediction?.trace_id === 'string' && prediction.trace_id.includes('demo-')
}
