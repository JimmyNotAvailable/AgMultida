import { describe, expect, it } from 'vitest'
import { getUncertaintyBadgeColor, isDemoPrediction } from './usePredictionFlow'

describe('usePredictionFlow helpers', () => {
  it('maps uncertainty to badge colors', () => {
    expect(getUncertaintyBadgeColor(0.1)).toBe('green')
    expect(getUncertaintyBadgeColor(0.2)).toBe('yellow')
    expect(getUncertaintyBadgeColor(0.31)).toBe('red')
  })

  it('detects demo predictions from trace id', () => {
    expect(isDemoPrediction({ trace_id: 'demo-A01-predict' } as never)).toBe(true)
    expect(isDemoPrediction({ trace_id: '1234' } as never)).toBe(false)
  })
})
