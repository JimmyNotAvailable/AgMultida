import { Link } from 'react-router-dom'
import { ThemeToggle } from '../../../components/shared/ThemeToggle'
import { isInternalRoutesEnabled } from '../../../lib/auth/guard'
import type { AlertRecord, IrrigationDecision } from '../../../lib/api/types'
import { useZoneReport } from '../useZoneReport'

export function ReportsPage() {
  const { zonesQuery, reportQuery } = useZoneReport()
  const report = reportQuery.data
  const isLoading = zonesQuery.isLoading || reportQuery.isLoading
  const isError = zonesQuery.isError || reportQuery.isError
  const showAdminLink = isInternalRoutesEnabled()

  return (
    <div className="field-dashboard-shell">
      <header className="field-topbar">
        <div className="field-container field-topbar-inner">
          <div className="field-brand"><span className="field-brand-mark">A</span><span className="field-brand-name">AgMultida</span></div>
          <nav className="field-nav" aria-label="Điều hướng chính"><Link to="/">Tổng quan</Link><Link to="/dashboard">Bản đồ & Giám sát</Link><Link className="active" to="/reports">Báo cáo</Link>{showAdminLink ? <Link to="/admin">Cài đặt</Link> : null}</nav>
          <div className="field-actions"><span className="field-badge warn"><span />Snapshot</span><ThemeToggle /></div>
        </div>
      </header>

      <main className="field-container field-main">
        <section className="field-hero reveal-card">
          <div className="field-hero-copy">
            <p className="field-kicker">Báo cáo vận hành / Zone nghiêm trọng</p>
            <h1>Báo cáo <em>giám sát</em></h1>
            <p>Tổng hợp các vấn đề nghiêm trọng đang phát sinh tại zone theo dõi và snapshot lệnh vận hành liên quan.</p>
          </div>
          <div className="field-filters report-summary" data-testid="report-summary">
            <Metric label="Zone nghiêm trọng" value={report?.summary.seriousZoneCount ?? 0} />
            <Metric label="Cảnh báo mở" value={report?.summary.openAlertCount ?? 0} />
            <Metric label="Snapshot lệnh" value={report?.summary.commandSnapshotCount ?? 0} />
            <Metric label="Zone lỗi tải" value={report?.summary.failedZoneCount ?? 0} />
          </div>
        </section>

        {isLoading ? <section className="field-card reveal-card">Đang tải báo cáo...</section> : null}
        {isError ? <section className="field-card reveal-card field-error" role="alert">Không thể tải báo cáo zone.</section> : null}
        {!isLoading && !isError && report ? <ReportContent report={report} /> : null}
      </main>
    </div>
  )
}

function ReportContent({ report }: { report: NonNullable<ReturnType<typeof useZoneReport>['reportQuery']['data']> }) {
  return (
    <section className="field-grid reports-grid">
      <div className="field-left-stack">
        <article className="field-card reveal-card">
          <div className="field-card-head compact"><h2>Vấn đề nghiêm trọng theo zone</h2><span className="field-badge danger">critical / degraded</span></div>
          {report.issues.length === 0 ? <p>Không có zone nào đang phát sinh vấn đề nghiêm trọng.</p> : null}
          <div className="report-zone-list" data-testid="serious-zone-list">
            {report.issues.map((issue) => (
              <article className="report-zone-card" key={issue.zone.id}>
                <div><h3>{issue.zone.name}</h3><p>{issue.zone.province} · {issue.zone.crop} · cập nhật {formatDate(issue.status?.updated_at)}</p></div>
                <div className="report-alert-list">
                  {issue.alerts.map((alert) => <AlertItem alert={alert} key={alert.alert_id} />)}
                </div>
              </article>
            ))}
          </div>
        </article>
      </div>

      <aside className="field-right-stack">
        <article className="field-card reveal-card">
          <div className="field-card-head compact"><h2>Lệnh đã thực thi</h2><span className="field-badge warn">snapshot hiện tại</span></div>
          <p>Hệ thống chưa có lịch sử lệnh đa zone, nên phần này hiển thị trạng thái lệnh/khuyến nghị gần nhất từ từng zone.</p>
          <div className="command-snapshot-list" data-testid="command-snapshot-list">
            {report.commands.length === 0 ? <p>Chưa có snapshot lệnh.</p> : null}
            {report.commands.map((command) => (
              <article className="command-snapshot" key={command.zoneId}>
                <div><strong>{command.zoneName}</strong><span>{command.state ?? 'NO_STATE'}</span></div>
                <p>{formatDecision(command.decision)}</p>
                <small>Cập nhật {formatDate(command.updatedAt)}</small>
              </article>
            ))}
          </div>
        </article>
      </aside>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="metric-tile"><span>{label}</span><strong>{value}</strong><small>theo dõi realtime</small></div>
}

function AlertItem({ alert }: { alert: AlertRecord }) {
  return <div className="report-alert"><span className={`field-badge ${alert.severity === 'critical' ? 'danger' : 'warn'}`}>{alert.severity}</span><p>{alert.message}</p><small>{formatDate(alert.timestamp)} · {alert.acknowledged ? 'đã xác nhận' : 'đang mở'}</small></div>
}

function formatDecision(decision: IrrigationDecision | null): string {
  if (!decision) return 'Chưa có khuyến nghị gần nhất.'
  return `${formatAction(decision.action)} · ${decision.volume_mm} mm · ${decision.reason}`
}

function formatAction(action: IrrigationDecision['action']): string {
  const labels: Record<IrrigationDecision['action'], string> = {
    no_irrigation: 'Không tưới',
    light: 'Tưới nhẹ',
    moderate: 'Tưới vừa',
    heavy: 'Tưới nhiều',
    hold: 'Giữ lệnh',
  }
  return labels[action]
}

function formatDate(value: string | null | undefined): string {
  if (!value) return 'không rõ'
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
}
