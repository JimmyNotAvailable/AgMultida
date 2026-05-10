import { useQuery } from '@tanstack/react-query'
import { getZones } from '../../lib/api'
import type { ZoneRegistryResponse } from '../../lib/api/types'
import { zones as fallbackZones, type ZoneData, type ZoneState } from './dashboardData'

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
