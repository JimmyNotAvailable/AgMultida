import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { DegradationBanner } from './DegradationBanner'
import type { PredictResponse } from '../../../lib/api/types'

afterEach(() => {
  cleanup()
})

function makePrediction(overrides: Partial<PredictResponse> = {}): PredictResponse {
  return {
    zone_id: 'A01',
    timestamp: '2026-05-10T10:15:00Z',
    stress_prob: 0.42,
    uncertainty: 0.12,
    confidence_flag: 'high',
    degraded_mode: false,
    attention_weights: [0.4, 0.3, 0.3],
    model_version: 'v1.0.0',
    latency_ms: 42.0,
    ...overrides,
  }
}

describe('DegradationBanner', () => {
  test('renders nothing when prediction is null', () => {
    const { container } = render(<DegradationBanner prediction={null} />)
    expect(container.innerHTML).toBe('')
  })

  test('renders nothing for normal healthy prediction', () => {
    const { container } = render(<DegradationBanner prediction={makePrediction()} />)
    expect(container.innerHTML).toBe('')
  })

  test('renders demo banner when trace_id contains demo prefix', () => {
    render(<DegradationBanner prediction={makePrediction({ trace_id: 'demo-A01-predict' })} />)
    expect(screen.getByText('Demo prediction. Backend unavailable.')).toBeTruthy()
  })

  test('renders degraded banner when degraded_mode is true', () => {
    render(<DegradationBanner prediction={makePrediction({ degraded_mode: true })} />)
    expect(screen.getByText('Prediction degraded. Low-confidence fallback active.')).toBeTruthy()
  })

  test('demo banner takes priority over degraded banner', () => {
    render(<DegradationBanner prediction={makePrediction({ trace_id: 'demo-A01-predict', degraded_mode: true })} />)
    expect(screen.getByText('Demo prediction. Backend unavailable.')).toBeTruthy()
    expect(screen.queryByText('Prediction degraded. Low-confidence fallback active.')).toBeNull()
  })

  test('banner uses data-card and degraded-banner-card classes', () => {
    render(<DegradationBanner prediction={makePrediction({ degraded_mode: true })} />)
    const article = screen.getByRole('article')
    expect(article.className).toContain('data-card')
    expect(article.className).toContain('degraded-banner-card')
  })
})
