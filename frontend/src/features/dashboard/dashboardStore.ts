import { useQuery } from '@tanstack/react-query'
import { getZones } from '../../lib/api'
import type { ZoneRegistryResponse } from '../../lib/api/types'
import type { WebSocketStatus } from '../../lib/realtime/types'
import { zones as fallbackZones, type ZoneData, type ZoneState } from './dashboardData'

interface DashboardState {
  wsStatus: WebSocketStatus
}

interface DashboardStoreState extends DashboardState {
  setWsStatus: (status: WebSocketStatus) => void
}

export const dashboardStore = createDashboardStore()

function createDashboardStore() {
  let state: DashboardState = { wsStatus: 'offline' }
  return {
    getState(): DashboardStoreState {
      return {
        ...state,
        setWsStatus(status: WebSocketStatus): void {
          state = { ...state, wsStatus: status }
        },
      }
    },
    setState(next: Partial<DashboardState>): void {
      state = { ...state, ...next }
    },
  }
}

export function connectionStatusLabel(status: WebSocketStatus): string {
  if (status === 'live') return 'Live'
  if (status === 'reconnecting') return 'Reconnecting'
  return 'Offline'
}

export function shouldUsePollingFallback(status: WebSocketStatus): boolean {
  return status !== 'live'
}

export function useDashboardZones() {
  return useQuery({
    queryKey: ['dashboard-zones'],
    queryFn: getZones,
    select: toDashboardZones,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function toDashboardZones(response: ZoneRegistryResponse): ZoneData[] {
  const fallbackById = new Map(fallbackZones.map((zone) => [zone.id, zone]))
  return response.zones.map((item, index) => {
    const fallback = fallbackById.get(item.zone.zone_id) ?? fallbackZones[index % fallbackZones.length]
    return {
      ...fallback,
      id: item.zone.zone_id,
      label: `Zone ${item.zone.zone_id}`,
      name: item.zone.zone_name,
      province: item.zone.province,
      crop: item.zone.crop_type,
      state: deriveZoneState(fallback.stress),
      note: item.bounds ? `bounds ${item.bounds.min_lng.toFixed(2)}, ${item.bounds.min_lat.toFixed(2)}` : fallback.note,
    }
  })
}

function deriveZoneState(stress: number): ZoneState {
  if (stress >= 0.65) return 'critical'
  if (stress >= 0.4) return 'moderate'
  return 'healthy'
}
