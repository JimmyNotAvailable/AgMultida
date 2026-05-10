import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { getWsUrl } from '../api/client'
import { dashboardStore } from '../../features/dashboard/dashboardStore'
import type { RealtimeEvent } from './types'

const MAX_RECONNECT_DELAY_MS = 30_000

export function getNextReconnectDelay(attempt: number): number {
  return Math.min(1000 * (2 ** attempt), MAX_RECONNECT_DELAY_MS)
}

export async function handleRealtimeEvent(queryClient: QueryClient, event: RealtimeEvent): Promise<void> {
  const zoneId = typeof event.payload.zone_id === 'string' ? event.payload.zone_id : null
  if (!zoneId) return

  if (event.event === 'prediction_completed' || event.event === 'status_changed' || event.event === 'recommendation_created') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-status', zoneId] })
  }
  if (event.event === 'alert_opened' || event.event === 'alert_acknowledged') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-alerts', zoneId] })
  }
  if (event.event === 'imagery_updated') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-imagery-latest', zoneId] })
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-imagery-history', zoneId] })
  }
}

export function useWebSocket(zoneId: string): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    let socket: WebSocket | null = null
    let stopped = false
    let reconnectAttempt = 0
    let reconnectTimer: number | null = null

    const connect = () => {
      dashboardStore.getState().setWsStatus(reconnectAttempt === 0 ? 'reconnecting' : 'offline')
      socket = new WebSocket(getWsUrl())
      socket.onopen = () => {
        reconnectAttempt = 0
        dashboardStore.getState().setWsStatus('live')
        socket?.send(JSON.stringify({ event: 'subscribe', payload: { zones: [zoneId] } }))
      }
      socket.onmessage = (message) => {
        try {
          void handleRealtimeEvent(queryClient, JSON.parse(message.data) as RealtimeEvent)
        } catch {
          return
        }
      }
      socket.onclose = () => {
        if (stopped) return
        dashboardStore.getState().setWsStatus('reconnecting')
        const delay = getNextReconnectDelay(reconnectAttempt)
        reconnectAttempt += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }
      socket.onerror = () => {
        socket?.close()
      }
    }

    connect()

    return () => {
      stopped = true
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      socket?.close()
      dashboardStore.getState().setWsStatus('offline')
    }
  }, [queryClient, zoneId])
}
