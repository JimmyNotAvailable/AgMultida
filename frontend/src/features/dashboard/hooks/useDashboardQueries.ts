import { useQuery } from '@tanstack/react-query'
import { getZoneImageryHistorySafe, getZoneImageryLatestSafe, getZoneSpectralSafe } from '../../../lib/api'

export const ZONE_STATUS_STALE_MS = 120_000
const IMAGERY_STALE_TIME_MS = 5 * 60_000
const SPECTRAL_STALE_TIME_MS = 10 * 60_000

export function useDashboardQueries(zoneId: string) {

  const imageryLatestQuery = useQuery({
    queryKey: ['dashboard-zone-imagery-latest', zoneId],
    queryFn: () => getZoneImageryLatestSafe(zoneId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    staleTime: IMAGERY_STALE_TIME_MS,
    gcTime: 15 * 60_000,
    retry: 1,
  })

  const imageryHistoryQuery = useQuery({
    queryKey: ['dashboard-zone-imagery-history', zoneId],
    queryFn: () => getZoneImageryHistorySafe(zoneId, 10),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    staleTime: IMAGERY_STALE_TIME_MS,
    gcTime: 15 * 60_000,
    retry: 1,
  })

  const spectralQuery = useQuery({
    queryKey: ['dashboard-zone-spectral', zoneId],
    queryFn: () => getZoneSpectralSafe(zoneId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    staleTime: SPECTRAL_STALE_TIME_MS,
    gcTime: 30 * 60_000,
    retry: 1,
  })

  return { imageryLatestQuery, imageryHistoryQuery, spectralQuery }
}

export function isZoneStatusStale(updatedAt: string | null | undefined, now = Date.now()): boolean {
  if (!updatedAt) return true
  return now - new Date(updatedAt).getTime() > ZONE_STATUS_STALE_MS
}
