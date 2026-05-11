import type { AlertRecord, CommandStatus, IrrigationDecision, ZoneStatusResponse } from '../../lib/api/types'
import type { ZoneData } from '../dashboard/dashboardData'

export interface ZoneReportInput {
  zone: ZoneData
  status: ZoneStatusResponse | null
  alerts: AlertRecord[]
  error?: boolean
}

export interface SeriousZoneIssue {
  zone: ZoneData
  alerts: AlertRecord[]
  status: ZoneStatusResponse | null
  command: CommandSnapshot | null
}

export interface CommandSnapshot {
  zoneId: string
  zoneName: string
  state: CommandStatus | null
  decision: IrrigationDecision | null
  updatedAt: string | null
}

export interface ZoneReportSummary {
  seriousZoneCount: number
  openAlertCount: number
  commandSnapshotCount: number
  failedZoneCount: number
}

export interface ZoneReport {
  issues: SeriousZoneIssue[]
  commands: CommandSnapshot[]
  summary: ZoneReportSummary
}

const SERIOUS_SEVERITIES = new Set<AlertRecord['severity']>(['critical', 'degraded'])

export function buildZoneReport(inputs: ZoneReportInput[]): ZoneReport {
  const issues = inputs
    .map((input) => {
      const alerts = getSeriousAlerts(mergeAlerts(input.alerts, input.status?.alerts ?? []))
      return {
        zone: input.zone,
        alerts,
        status: input.status,
        command: buildCommandSnapshot(input),
      }
    })
    .filter((issue) => issue.alerts.length > 0)

  const commands = inputs
    .map(buildCommandSnapshot)
    .filter((command): command is CommandSnapshot => command !== null)

  return {
    issues,
    commands,
    summary: {
      seriousZoneCount: issues.length,
      openAlertCount: issues.flatMap((issue) => issue.alerts).filter((alert) => !alert.acknowledged).length,
      commandSnapshotCount: commands.length,
      failedZoneCount: inputs.filter((input) => input.error).length,
    },
  }
}

function mergeAlerts(primaryAlerts: AlertRecord[], fallbackAlerts: AlertRecord[]): AlertRecord[] {
  const byId = new Map<string, AlertRecord>()
  ;[...primaryAlerts, ...fallbackAlerts].forEach((alert) => {
    byId.set(alert.alert_id, alert)
  })
  return [...byId.values()]
}

export function getSeriousAlerts(alerts: AlertRecord[]): AlertRecord[] {
  return [...alerts]
    .filter((alert) => SERIOUS_SEVERITIES.has(alert.severity))
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
}

function buildCommandSnapshot(input: ZoneReportInput): CommandSnapshot | null {
  if (!input.status?.latest_decision && !input.status?.command_state) {
    return null
  }

  return {
    zoneId: input.zone.id,
    zoneName: input.zone.name,
    state: input.status.command_state ?? null,
    decision: input.status.latest_decision ?? null,
    updatedAt: input.status.updated_at ?? null,
  }
}
