import { useMutation, useQueryClient } from '@tanstack/react-query'
import { acknowledgeAlert } from '../../../lib/api'
import type { AlertRecord } from '../../../lib/api/types'

type AlertFeedProps = {
  zoneId: string
  alerts: AlertRecord[]
  isLoading: boolean
  isError: boolean
  onSelectZone: (zoneId: string) => void
}

const severityClassName: Record<string, string> = {
  critical: 'alert-critical',
  moderate: 'alert-moderate',
  watch: 'alert-watch',
}

export function AlertFeed({ zoneId, alerts, isLoading, isError, onSelectZone }: AlertFeedProps) {
  const queryClient = useQueryClient()
  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => acknowledgeAlert(alertId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['dashboard-zone-alerts', zoneId] })
    },
  })

  if (isLoading) {
    return <div>Loading alerts...</div>
  }

  if (isError) {
    return <div>Alerts unavailable</div>
  }

  if (alerts.length === 0) {
    return <div>No open alerts</div>
  }

  return (
    <div>
      {alerts.map((alert) => (
        <article key={alert.alert_id} className={severityClassName[alert.severity] ?? 'alert-watch'}>
          <div>{alert.message}</div>
          <div>{alert.severity}</div>
          <button type="button" aria-label={`Pan map to ${alert.zone_id}`} onClick={() => onSelectZone(alert.zone_id)}>
            View zone
          </button>
          {!alert.acknowledged ? (
            <button
              type="button"
              aria-label={`Acknowledge alert ${alert.alert_id}`}
              onClick={() => acknowledgeMutation.mutate(alert.alert_id)}
              disabled={acknowledgeMutation.isPending}
            >
              Acknowledge
            </button>
          ) : null}
        </article>
      ))}
    </div>
  )
}
