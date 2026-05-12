import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { getWsUrl } from '../api/client'
import { dashboardStore } from '../../features/dashboard/dashboardStore'
import type { RealtimeEvent } from './types'

const MAX_RECONNECT_DELAY_MS = 30_000
const INITIAL_RECONNECT_DELAY_MS = 5_000
const REALTIME_DEDUPE_WINDOW_MS = 2_000
const MAX_RECENT_REALTIME_EVENTS = 256
const recentRealtimeEvents = new Map<string, number>()
const DEDUPED_REALTIME_EVENTS = new Set(['alert_created', 'alert_opened', 'alert_acknowledged'])

export function getNextReconnectDelay(attempt: number): number {
  return Math.min(INITIAL_RECONNECT_DELAY_MS * (2 ** attempt), MAX_RECONNECT_DELAY_MS)
}

function parseRealtimeEvent(data: string): RealtimeEvent | null {
  const value: unknown = JSON.parse(data)
  if (typeof value !== 'object' || value === null) return null
  const event = value as Partial<RealtimeEvent>
  if (typeof event.event !== 'string' || typeof event.payload !== 'object' || event.payload === null) return null
  return event as RealtimeEvent
}

export async function handleRealtimeEvent(queryClient: QueryClient, event: RealtimeEvent, now = Date.now()): Promise<void> {
  const zoneId = typeof event.payload.zone_id === 'string' ? event.payload.zone_id : null
  if (!zoneId) return
  if (DEDUPED_REALTIME_EVENTS.has(event.event) && isDuplicateRealtimeEvent(event, zoneId, now)) return

  if (event.event === 'prediction_completed' || event.event === 'status_changed' || event.event === 'recommendation_created') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-status', zoneId] })
  }
  if (event.event === 'alert_created' || event.event === 'alert_opened' || event.event === 'alert_acknowledged') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-alerts', zoneId] })
  }
  if (event.event === 'imagery_updated') {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-imagery-latest', zoneId] })
    await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-imagery-history', zoneId] })
  }
}

function isDuplicateRealtimeEvent(event: RealtimeEvent, zoneId: string, now: number): boolean {
  const alertId = typeof event.payload.alert_id === 'string' ? event.payload.alert_id : ''
  const predictionId = typeof event.payload.prediction_id === 'string' ? event.payload.prediction_id : ''
  const action = typeof event.payload.action === 'string' ? event.payload.action : ''
  const eventKey = [event.event, zoneId, alertId, predictionId, action].join(':')
  const previous = recentRealtimeEvents.get(eventKey)

  for (const [key, timestamp] of recentRealtimeEvents) {
    if (now - timestamp > REALTIME_DEDUPE_WINDOW_MS || recentRealtimeEvents.size >= MAX_RECENT_REALTIME_EVENTS) {
      recentRealtimeEvents.delete(key)
    }
  }
  recentRealtimeEvents.set(eventKey, now)

  return previous !== undefined && now - previous <= REALTIME_DEDUPE_WINDOW_MS
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
          const event = parseRealtimeEvent(message.data)
          if (event) void handleRealtimeEvent(queryClient, event)
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
