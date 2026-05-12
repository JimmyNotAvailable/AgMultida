import { useQuery } from '@tanstack/react-query'
import { getZoneAlerts, getZoneStatus } from '../../lib/api'
import { useDashboardZones } from '../dashboard/dashboardStore'
import { buildZoneReport } from './reportModel'

const REPORT_STALE_TIME_MS = 60_000

export function useZoneReport() {
  const zonesQuery = useDashboardZones()
  const zoneIds = zonesQuery.data?.map((zone) => zone.id) ?? []

  const reportQuery = useQuery({
    queryKey: ['zone-report', zoneIds],
    enabled: zoneIds.length > 0,
    queryFn: async () => {
      const zones = zonesQuery.data ?? []
      const rows = await Promise.all(zones.map(async (zone) => {
        try {
          const [status, alertFeed] = await Promise.all([
            getZoneStatus(zone.id),
            getZoneAlerts(zone.id),
          ])
          return { zone, status, alerts: alertFeed.alerts }
        } catch {
          return { zone, status: null, alerts: [], error: true }
        }
      }))
      return buildZoneReport(rows)
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    staleTime: REPORT_STALE_TIME_MS,
    gcTime: 10 * 60_000,
    retry: 1,
  })

  return {
    zonesQuery,
    reportQuery,
  }
}
