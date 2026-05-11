import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { LanguageProvider } from '../../../lib/i18n/useLanguage'
import { AdminPage } from './AdminPage'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

test('admin readiness panel sanitizes upstream errors', async () => {
  mockFetch({
    '/v1/healthz': { status: 'ok', version: '1.0.0', timestamp: '2024-02-14T03:21:00Z' },
    '/v1/zones': zoneListFixture(),
    '/v1/readyz': {
      status: 'degraded',
      mode: 'live',
      dependencies: {
        ai_serving: {
          status: 'degraded',
          upstream_last_error: 'http://internal/service stack trace secret-token',
          checked_at: '2024-02-14T03:21:00Z',
        },
      },
    },
    '/v1/zones/A01/status': zoneStatusFixture(),
  })

  renderAdminPage()

  await waitFor(() => expect(screen.getByTestId('readiness-panel').textContent).toContain('Dependency unavailable'))
  expect(screen.getByTestId('readiness-panel').textContent).not.toContain('secret-token')
})

test('admin zone status renders sanitized zone summary', async () => {
  mockFetch({
    '/v1/healthz': { status: 'ok', version: '1.0.0', timestamp: '2024-02-14T03:21:00Z' },
    '/v1/zones': zoneListFixture(),
    '/v1/readyz': { status: 'ok', mode: 'stub', dependencies: {} },
    '/v1/zones/A01/status': zoneStatusFixture(),
  })

  renderAdminPage()

  await waitFor(() => expect(screen.getByTestId('zone-status-panel').textContent).toContain('A01'))
  expect(screen.getByTestId('zone-status-panel').textContent).toContain('moderate')
  expect(screen.getByTestId('zone-status-panel').textContent).toContain('Available')
})

test('admin table renders multiple zones and row click seeds forms', async () => {
  mockFetch({
    '/v1/healthz': { status: 'ok', version: '1.0.0', timestamp: '2024-02-14T03:21:00Z' },
    '/v1/zones': zoneListFixture(),
    '/v1/readyz': { status: 'ok', mode: 'stub', dependencies: {} },
    '/v1/zones/A01/status': zoneStatusFixture(),
    '/v1/zones/D01/status': { ...zoneStatusFixture(), zone_id: 'D01' },
  })

  renderAdminPage()

  await waitFor(() => expect(screen.getByTestId('zone-table').textContent).toContain('TN01'))
  fireEvent.click(screen.getByTestId('zone-row-D01'))

  await waitFor(() => expect(screen.getAllByDisplayValue('D01').length).toBeGreaterThanOrEqual(3))
  await waitFor(() => expect(screen.getByTestId('zone-status-panel').textContent).toContain('D01'))
})

test('admin runner chains predict to recommend to command', async () => {
  const fetchMock = mockFetch({
    '/v1/healthz': { status: 'ok', version: '1.0.0', timestamp: '2024-02-14T03:21:00Z' },
    '/v1/zones': zoneListFixture(),
    '/v1/readyz': { status: 'ok', mode: 'stub', dependencies: {} },
    '/v1/zones/A01/status': zoneStatusFixture(),
    '/v1/predict': predictFixture(),
    '/v1/recommend': recommendationFixture(),
    '/v1/commands': {
      trace_id: 'trace-command',
      command_id: 'cmd_12345678',
      zone_id: 'A01',
      status: 'pending',
      timestamp: '2024-02-14T03:25:00Z',
    },
  })

  renderAdminPage()

  fireEvent.click(screen.getByText('Run Predict'))
  await waitFor(() => expect(screen.getByTestId('predict-panel').textContent).toContain('model-v1'))

  fireEvent.click(screen.getByText('Run Recommend'))
  await waitFor(() => expect(screen.getByTestId('recommend-panel').textContent).toContain('moderate'))

  fireEvent.click(screen.getByText('Send Command'))
  await waitFor(() => expect(screen.getByTestId('command-panel').textContent).toContain('cmd_12345678'))

  expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/predict', expect.objectContaining({ method: 'POST' }))
  expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/recommend', expect.objectContaining({ method: 'POST' }))
  expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/commands', expect.objectContaining({ method: 'POST' }))
})

function renderAdminPage() {
  import.meta.env.VITE_ENABLE_INTERNAL_ROUTES = 'true'
  import.meta.env.VITE_DEV_ACCESS_TOKEN = 'test-token'
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

  render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <AdminPage />
      </LanguageProvider>
    </QueryClientProvider>,
  )
}

function mockFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input.toString())
    const body = routes[url.pathname]

    if (!body) {
      return new Response(JSON.stringify({ message: 'missing mock' }), { status: 404 })
    }

    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function zoneListFixture() {
  return {
    trace_id: 'trace-zones',
    zones: [
      {
        zone: {
          zone_id: 'A01',
          zone_name: 'Mỹ Thiện',
          province: 'Đồng Tháp',
          crop_type: 'rice',
          split: 'train',
          local_timezone: 'Asia/Ho_Chi_Minh',
        },
        command_state: null,
        confidence_flag: 'medium',
        degraded_mode: false,
        updated_at: '2024-02-14T03:24:00Z',
      },
      {
        zone: {
          zone_id: 'TN01',
          zone_name: 'Mộc Hoá',
          province: 'Tây Ninh',
          crop_type: 'rice',
          split: 'train',
          local_timezone: 'Asia/Ho_Chi_Minh',
        },
        command_state: null,
        confidence_flag: 'low',
        degraded_mode: true,
        updated_at: '2024-02-14T03:24:00Z',
      },
      {
        zone: {
          zone_id: 'D01',
          zone_name: 'Dong Thap validation zone D01',
          province: 'Dong Thap',
          crop_type: 'rice',
          split: 'val',
          local_timezone: 'Asia/Ho_Chi_Minh',
        },
        command_state: 'PENDING',
        confidence_flag: null,
        degraded_mode: false,
        updated_at: '2024-02-14T03:24:00Z',
      },
    ],
  }
}

function zoneStatusFixture() {
  return {
    trace_id: 'trace-zone',
    zone_id: 'A01',
    latest_prediction: predictFixture(),
    latest_decision: recommendationFixture(),
    latest_telemetry: { sensor: 'hidden-detail' },
    command_state: 'pending',
    updated_at: '2024-02-14T03:24:00Z',
  }
}

function predictFixture() {
  return {
    trace_id: 'trace-predict',
    zone_id: 'A01',
    timestamp: '2024-02-14T03:21:00Z',
    stress_prob: 0.74,
    uncertainty: 0.18,
    confidence_flag: 'medium',
    degraded_mode: false,
    attention_weights: [0.6, 0.4],
    model_version: 'model-v1',
    explanation: [{ feature: 'soil_moisture', weight: 0.7, trend: 'drying' }],
    latency_ms: 42,
  }
}

function recommendationFixture() {
  return {
    trace_id: 'trace-rec',
    action: 'moderate',
    volume_mm: 12,
    require_ack: true,
    reason: 'moderate stress',
    safety_override: false,
    degraded_mode: false,
    confidence_flag: 'medium',
    explanation: [{ feature: 'stress_prob', weight: 0.8, trend: 'rising' }],
  }
}
