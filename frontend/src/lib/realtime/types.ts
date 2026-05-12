export type WebSocketStatus = 'live' | 'reconnecting' | 'offline'

export interface RealtimeEvent {
  event: string
  payload: Record<string, unknown>
  ts: string
  trace_id: string
}
