import { QueryClient } from '@tanstack/react-query'
import { expect, test, vi } from 'vitest'
import { handleRealtimeEvent, getNextReconnectDelay } from './useWebSocket'
import { dashboardStore } from '../../features/dashboard/dashboardStore'

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
