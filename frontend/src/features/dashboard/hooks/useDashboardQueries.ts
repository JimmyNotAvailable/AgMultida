import { useQuery } from '@tanstack/react-query'
import { getZoneAlerts, getZoneImageryHistorySafe, getZoneImageryLatestSafe, getZoneStatus } from '../../../lib/api'

export const ZONE_STATUS_STALE_MS = 120_000

export function useDashboardQueries(zoneId: string) {
  const statusQuery = useQuery({
    queryKey: ['dashboard-zone-status', zoneId],
    queryFn: () => getZoneStatus(zoneId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30_000,
  })

  const alertsQuery = useQuery({
    queryKey: ['dashboard-zone-alerts', zoneId],
    queryFn: async () => (await getZoneAlerts(zoneId)).alerts,
    refetchInterval: 30000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const imageryLatestQuery = useQuery({
    queryKey: ['dashboard-zone-imagery-latest', zoneId],
    queryFn: () => getZoneImageryLatestSafe(zoneId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const imageryHistoryQuery = useQuery({
    queryKey: ['dashboard-zone-imagery-history', zoneId],
    queryFn: () => getZoneImageryHistorySafe(zoneId, 10),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  return { statusQuery, alertsQuery, imageryLatestQuery, imageryHistoryQuery }
}

export function isZoneStatusStale(updatedAt: string | null | undefined, now = Date.now()): boolean {
  if (!updatedAt) return true
  return now - new Date(updatedAt).getTime() > ZONE_STATUS_STALE_MS
}
