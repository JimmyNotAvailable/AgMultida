import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AlertFeed } from './AlertFeed'
import type { AlertRecord } from '../../../lib/api/types'

const baseAlert: AlertRecord = {
  alert_id: 'alert-1',
  zone_id: 'A01',
  rule_id: 'irrigation_action',
  severity: 'moderate',
  source: 'alert_lifecycle',
  message: 'Recommended action: moderate',
  acknowledged: false,
  timestamp: '2026-04-29T03:35:11.963000Z',
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderFeed(props: Partial<Parameters<typeof AlertFeed>[0]> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AlertFeed
        zoneId="A01"
        alerts={[]}
        isLoading={false}
        isError={false}
        onSelectZone={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  )
}

test('renders loading and empty alert states', () => {
  renderFeed({ isLoading: true })
  expect(screen.getByText('Loading alerts...')).toBeTruthy()
  cleanup()

  renderFeed()
  expect(screen.getByText('No open alerts')).toBeTruthy()
})

test('renders error fallback without blocking UI', () => {
  renderFeed({ isError: true })
  expect(screen.getByText('Alerts unavailable')).toBeTruthy()
})

test('acknowledges alert and invalidates query without page reload', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ...baseAlert, acknowledged: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  renderFeed({ alerts: [baseAlert] })

  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge alert alert-1' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/v1/alerts/alert-1/ack'), expect.objectContaining({ method: 'POST' })))
})

test('clicking alert pans map to zone', () => {
  const onSelectZone = vi.fn()
  renderFeed({ alerts: [baseAlert], onSelectZone })

  fireEvent.click(screen.getByRole('button', { name: 'Pan map to A01' }))

  expect(onSelectZone).toHaveBeenCalledWith('A01')
})

test('severity class maps to correct CSS class', () => {
  const criticalAlert: AlertRecord = { ...baseAlert, alert_id: 'a-crit', severity: 'critical' }
  const watchAlert: AlertRecord = { ...baseAlert, alert_id: 'a-watch', severity: 'watch' }
  renderFeed({ alerts: [criticalAlert, watchAlert] })

  const articles = screen.getAllByRole('article')
  expect(articles[0].className).toContain('alert-critical')
  expect(articles[1].className).toContain('alert-watch')
})

test('acknowledged alert hides acknowledge button', () => {
  const ackedAlert: AlertRecord = { ...baseAlert, acknowledged: true }
  renderFeed({ alerts: [ackedAlert] })

  expect(screen.queryByRole('button', { name: /Acknowledge/ })).toBeNull()
  expect(screen.getByRole('button', { name: 'Pan map to A01' })).toBeTruthy()
})

test('acknowledge button disables during mutation', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}))
  renderFeed({ alerts: [baseAlert] })

  const btn = screen.getByRole('button', { name: 'Acknowledge alert alert-1' })
  fireEvent.click(btn)

  await waitFor(() => expect((btn as HTMLButtonElement).disabled).toBe(true))
})

test('multiple alerts render in order', () => {
  const alerts: AlertRecord[] = [
    { ...baseAlert, alert_id: 'a1', message: 'First alert' },
    { ...baseAlert, alert_id: 'a2', message: 'Second alert' },
    { ...baseAlert, alert_id: 'a3', message: 'Third alert' },
  ]
  renderFeed({ alerts })

  const articles = screen.getAllByRole('article')
  expect(articles).toHaveLength(3)
  expect(articles[0].textContent).toContain('First alert')
  expect(articles[2].textContent).toContain('Third alert')
})
