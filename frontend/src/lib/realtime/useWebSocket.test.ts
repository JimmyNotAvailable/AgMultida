import { QueryClient } from '@tanstack/react-query'
import { describe, expect, test, vi } from 'vitest'
import { handleRealtimeEvent, getNextReconnectDelay } from './useWebSocket'
import { dashboardStore, connectionStatusLabel, shouldUsePollingFallback } from '../../features/dashboard/dashboardStore'

test('prediction event invalidates zone status query', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'prediction_completed', payload: { zone_id: 'A01' }, ts: '2026-05-10T00:00:00Z', trace_id: 't1' })

  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-status', 'A01'] })
})

test('alert event invalidates alert query', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'alert_opened', payload: { zone_id: 'A01' }, ts: '2026-05-10T00:00:00Z', trace_id: 't1' })

  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-alerts', 'A01'] })
})

test('reconnect delay grows exponentially and caps at 30s', () => {
  expect(getNextReconnectDelay(0)).toBe(1000)
  expect(getNextReconnectDelay(1)).toBe(2000)
  expect(getNextReconnectDelay(2)).toBe(4000)
  expect(getNextReconnectDelay(10)).toBe(30000)
})

test('store updates ws status pill states', () => {
  dashboardStore.setState({ wsStatus: 'offline' })
  dashboardStore.getState().setWsStatus('live')
  expect(dashboardStore.getState().wsStatus).toBe('live')
  dashboardStore.getState().setWsStatus('reconnecting')
  expect(dashboardStore.getState().wsStatus).toBe('reconnecting')
})

test('recommendation_created event invalidates zone status', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'recommendation_created', payload: { zone_id: 'B07' }, ts: '2026-05-10T00:00:00Z', trace_id: 't2' })

  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-status', 'B07'] })
})

test('alert_acknowledged event invalidates alert query', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'alert_acknowledged', payload: { zone_id: 'A01' }, ts: '2026-05-10T00:00:00Z', trace_id: 't3' })

  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-alerts', 'A01'] })
})

test('imagery_updated event invalidates imagery queries', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'imagery_updated', payload: { zone_id: 'A01' }, ts: '2026-05-10T00:00:00Z', trace_id: 't4' })

  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-imagery-latest', 'A01'] })
  expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['dashboard-zone-imagery-history', 'A01'] })
})

test('event without zone_id is ignored', async () => {
  const queryClient = new QueryClient()
  const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue()

  await handleRealtimeEvent(queryClient, { event: 'prediction_completed', payload: {}, ts: '2026-05-10T00:00:00Z', trace_id: 't5' })

  expect(invalidateQueries).not.toHaveBeenCalled()
})

describe('WS disconnect polling fallback', () => {
  test('offline status triggers polling fallback', () => {
    expect(shouldUsePollingFallback('offline')).toBe(true)
  })

  test('reconnecting status triggers polling fallback', () => {
    expect(shouldUsePollingFallback('reconnecting')).toBe(true)
  })

  test('live status does not trigger polling fallback', () => {
    expect(shouldUsePollingFallback('live')).toBe(false)
  })

  test('connection status labels are correct', () => {
    expect(connectionStatusLabel('live')).toBe('Live')
    expect(connectionStatusLabel('reconnecting')).toBe('Reconnecting')
    expect(connectionStatusLabel('offline')).toBe('Offline')
  })
})
