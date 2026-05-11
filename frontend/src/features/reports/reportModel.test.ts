import { expect, test } from 'vitest'
import type { AlertRecord, IrrigationDecision, ZoneStatusResponse } from '../../lib/api/types'
import type { ZoneData } from '../dashboard/dashboardData'
import { buildZoneReport, getSeriousAlerts } from './reportModel'

const zone: ZoneData = {
  id: 'A01',
  label: 'Zone A01',
  name: 'An Giang A01',
  province: 'An Giang',
  crop: 'Rice',
  stress: 0.75,
  moisture: 18,
  rain: 0.1,
  uncertainty: 0.28,
  rec: 'heavy',
  volume: 24,
  state: 'critical',
  path: 'M0 0',
  note: 'critical watch',
}

const decision: IrrigationDecision = {
  action: 'heavy',
  volume_mm: 24,
  require_ack: true,
  reason: 'critical_stress_low_moisture',
  degraded_mode: false,
  confidence_flag: 'medium',
}

const status: ZoneStatusResponse = {
  zone_id: 'A01',
  latest_decision: decision,
  command_state: 'ACTIVE',
  updated_at: '2026-05-11T08:00:00Z',
}

test('filters serious alerts by severity and newest first', () => {
  const alerts = getSeriousAlerts([
    alert('watch-1', 'watch', '2026-05-11T07:00:00Z'),
    alert('critical-1', 'critical', '2026-05-11T08:00:00Z'),
    alert('degraded-1', 'degraded', '2026-05-11T09:00:00Z'),
  ])

  expect(alerts.map((item) => item.alert_id)).toEqual(['degraded-1', 'critical-1'])
})

test('builds zone report with serious issues and command snapshots only', () => {
  const report = buildZoneReport([
    { zone, status, alerts: [alert('critical-1', 'critical', '2026-05-11T08:00:00Z')] },
    { zone: { ...zone, id: 'A02', name: 'An Giang A02' }, status: null, alerts: [alert('info-1', 'info', '2026-05-11T08:00:00Z')] },
  ])

  expect(report.summary).toEqual({ seriousZoneCount: 1, openAlertCount: 1, commandSnapshotCount: 1, failedZoneCount: 0 })
  expect(report.issues[0].zone.id).toBe('A01')
  expect(report.commands[0]).toMatchObject({ zoneId: 'A01', zoneName: 'An Giang A01', state: 'ACTIVE', decision })
})

test('merges status alerts when feed has no serious severity', () => {
  const report = buildZoneReport([
    {
      zone,
      status: { ...status, alerts: [alert('critical-from-status', 'critical', '2026-05-11T10:00:00Z')] },
      alerts: [alert('info-from-feed', 'info', '2026-05-11T08:00:00Z')],
      error: true,
    },
  ])

  expect(report.summary.failedZoneCount).toBe(1)
  expect(report.issues[0].alerts.map((item) => item.alert_id)).toEqual(['critical-from-status'])
})










function alert(alertId: string, severity: AlertRecord['severity'], timestamp: string): AlertRecord {
  return {
    alert_id: alertId,
    zone_id: 'A01',
    rule_id: 'rule',
    severity,
    source: 'test',
    message: `${severity} message`,
    acknowledged: false,
    timestamp,
  }
}
