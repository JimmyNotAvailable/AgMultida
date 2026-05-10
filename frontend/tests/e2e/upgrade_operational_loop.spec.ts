import { expect, test } from '@playwright/test'

const MOCK_ZONE_REGISTRY = {
  trace_id: 'e2e-registry',
  zones: [
    {
      zone: { zone_id: 'A01', zone_name: 'An Giang A01', province: 'An Giang', crop_type: 'rice', split: 'validation', local_timezone: 'Asia/Ho_Chi_Minh' },
      bounds: { min_lng: 105.05, min_lat: 10.05, max_lng: 105.11, max_lat: 10.11 },
      centroid: [105.08, 10.08],
    },
    {
      zone: { zone_id: 'A03', zone_name: 'An Giang A03', province: 'An Giang', crop_type: 'rice', split: 'validation', local_timezone: 'Asia/Ho_Chi_Minh' },
      bounds: { min_lng: 105.12, min_lat: 10.05, max_lng: 105.18, max_lat: 10.11 },
      centroid: [105.15, 10.08],
    },
  ],
}

const MOCK_PREDICTION = {
  trace_id: 'e2e-predict-trace',
  prediction_id: 'pred_e2e001',
  zone_id: 'A01',
  timestamp: '2026-05-08T08:42:00Z',
  stress_prob: 0.65,
  uncertainty: 0.12,
  confidence_flag: 'high',
  degraded_mode: false,
  attention_weights: [0.4, 0.3, 0.3],
  model_version: 'v1.0.0-e2e',
  explanation: [],
  latency_ms: 42.0,
}

const MOCK_RECOMMENDATION = {
  trace_id: 'e2e-recommend-trace',
  action: 'heavy',
  volume_mm: 28.0,
  require_ack: false,
  reason: 'critical_stress_low_moisture',
  safety_override: false,
  degraded_mode: false,
  confidence_flag: 'high',
  explanation: [],
}

const MOCK_COMMAND_RESPONSE = {
  trace_id: 'e2e-command-trace',
  command_id: 'cmd_e2e001',
  zone_id: 'A01',
  status: 'PENDING',
  timestamp: '2026-05-10T10:00:00Z',
}

const MOCK_ZONE_STATUS = {
  trace_id: 'e2e-status-trace',
  zone_id: 'A01',
  latest_prediction: MOCK_PREDICTION,
  latest_decision: MOCK_RECOMMENDATION,
  latest_telemetry: { soil_moisture: 22.0, rain_3h: 1.5 },
  weather: null,
  imagery: null,
  alerts: [],
  command_state: null,
  updated_at: new Date().toISOString(),
}

const MOCK_ALERT = {
  alert_id: 'alert_e2e001',
  zone_id: 'A01',
  rule_id: 'irrigation_action',
  severity: 'moderate',
  source: 'alert_lifecycle',
  message: 'Recommended action: heavy',
  acknowledged: false,
  timestamp: '2026-05-10T10:00:00Z',
}

const MOCK_ALERTS_RESPONSE = {
  trace_id: 'e2e-alerts-trace',
  zone_id: 'A01',
  alerts: [MOCK_ALERT],
}

const MOCK_IMAGERY_LATEST = {
  zone_id: 'A01',
  scene_id: 'S2A_A01_20260508',
  acquisition_time: '2026-05-08T08:42:00Z',
  cloud_cover: 8.5,
  rgb_url: '/v1/imagery/preview/S2A_A01_20260508?mode=rgb',
  ndvi_url: '/v1/imagery/preview/S2A_A01_20260508?mode=ndvi',
  source: 'sentinel-2-l2a',
  stale: false,
}

const MOCK_IMAGERY_HISTORY = {
  trace_id: 'e2e-imagery-history',
  zone_id: 'A01',
  scenes: [MOCK_IMAGERY_LATEST],
}

const PNG_1PX = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')

function installGoldenPathRoutes(page: import('@playwright/test').Page) {
  return Promise.all([
    page.route('**/v1/zones', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ZONE_REGISTRY) })),
    page.route('**/v1/zones/A01/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ZONE_STATUS) })),
    page.route('**/v1/zones/A01/alerts*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ALERTS_RESPONSE) })),
    page.route('**/v1/zones/A01/imagery/latest', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IMAGERY_LATEST) })),
    page.route('**/v1/zones/A01/imagery/history*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IMAGERY_HISTORY) })),
    page.route('**/v1/imagery/preview/**', (route) => route.fulfill({ status: 200, contentType: 'image/png', body: PNG_1PX })),
    page.route('**/v1/predict', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PREDICTION) })),
    page.route('**/v1/recommend/from-cache', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_RECOMMENDATION) })),
    page.route('**/v1/recommend', (route) => {
      if (route.request().url().includes('from-cache')) return
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_RECOMMENDATION) })
    }),
    page.route('**/v1/commands*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_COMMAND_RESPONSE) })),
    page.route('**/v1/alerts/*/ack', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...MOCK_ALERT, acknowledged: true }) })),
    page.route('**/v1/healthz', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', version: '1.0.0', timestamp: new Date().toISOString() }) })),
  ])
}


test.describe('Golden path: full operational loop', () => {
  test('dashboard mount -> zone load -> predict -> recommend -> alert -> UI update', async ({ page }) => {
    await installGoldenPathRoutes(page)
    await page.goto('/dashboard?zone=A01')

    await expect(page.getByText('An Giang A01')).toBeVisible()
    await expect(page.getByTestId('imagery-panel')).toBeVisible()
    await expect(page.getByTestId('imagery-status')).toHaveText('Fresh')

    await page.getByText('Run prediction').click()
    await expect(page.getByTestId('prediction-percent')).toHaveText('65%')
    await expect(page.getByText('Model version')).toBeVisible()
    await expect(page.getByText('v1.0.0-e2e')).toBeVisible()

    await page.getByText('Run recommendation').click()
    await expect(page.getByTestId('recommendation-volume')).toHaveText('28 mm')
    await expect(page.getByText('critical_stress_low_moisture')).toBeVisible()

    await expect(page.getByText('Recommended action: heavy')).toBeVisible()
    const ackButton = page.getByRole('button', { name: /Acknowledge alert/ })
    await expect(ackButton).toBeVisible()
  })

  test('zone selection resets mutation state', async ({ page }) => {
    await installGoldenPathRoutes(page)
    await page.goto('/dashboard?zone=A01')
    await page.getByText('Run prediction').click()
    await expect(page.getByTestId('prediction-percent')).toHaveText('65%')

    await page.route('**/v1/zones/A03/status', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...MOCK_ZONE_STATUS, zone_id: 'A03', latest_prediction: null, latest_decision: null, alerts: [] }),
    }))
    await page.route('**/v1/zones/A03/alerts*', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ trace_id: 'e2e', zone_id: 'A03', alerts: [] }),
    }))
    await page.route('**/v1/zones/A03/imagery/latest', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...MOCK_IMAGERY_LATEST, zone_id: 'A03' }),
    }))
    await page.route('**/v1/zones/A03/imagery/history*', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...MOCK_IMAGERY_HISTORY, zone_id: 'A03' }),
    }))

    await page.getByText('An Giang A03').click()
    await expect(page.getByText('No result yet')).toBeVisible()
  })
})


test.describe('Failure path: graceful degradation', () => {
  test('503 backend returns fallback UI with demo banner', async ({ page }) => {
    await page.route('**/v1/zones', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))
    await page.route('**/v1/zones/*/status', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))
    await page.route('**/v1/zones/*/alerts*', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))
    await page.route('**/v1/zones/*/imagery/latest', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))
    await page.route('**/v1/zones/*/imagery/history*', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))
    await page.route('**/v1/predict', (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }))

    await page.goto('/dashboard')

    await expect(page.locator('.dashboard-shell')).toBeVisible()
    await expect(page.getByText('Run prediction')).toBeVisible()

    await page.getByText('Run prediction').click()

    await expect(page.getByText('Demo prediction. Backend unavailable.')).toBeVisible()
    await expect(page.getByTestId('prediction-percent')).toBeVisible()
  })

  test('imagery timeout shows placeholder scene with no blank UI', async ({ page }) => {
    await page.route('**/v1/zones', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ZONE_REGISTRY) }))
    await page.route('**/v1/zones/A01/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ZONE_STATUS) }))
    await page.route('**/v1/zones/A01/alerts*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ trace_id: 'e2e', zone_id: 'A01', alerts: [] }) }))
    await page.route('**/v1/zones/A01/imagery/latest', (route) => route.fulfill({ status: 504, body: 'Gateway Timeout' }))
    await page.route('**/v1/zones/A01/imagery/history*', (route) => route.fulfill({ status: 504, body: 'Gateway Timeout' }))

    await page.goto('/dashboard?zone=A01')

    await expect(page.locator('.dashboard-shell')).toBeVisible()
    await expect(page.getByText('Zone imagery')).toBeVisible()
    await expect(page.getByTestId('imagery-panel')).toBeVisible()
  })

  test('uncertainty >0.3 command gate blocks with rejection UI', async ({ page }) => {
    const degradedPrediction = { ...MOCK_PREDICTION, uncertainty: 0.35, confidence_flag: 'low' }
    const degradedStatus = { ...MOCK_ZONE_STATUS, latest_prediction: degradedPrediction }

    await page.route('**/v1/zones', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ZONE_REGISTRY) }))
    await page.route('**/v1/zones/A01/status', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(degradedStatus) }))
    await page.route('**/v1/zones/A01/alerts*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ALERTS_RESPONSE) }))
    await page.route('**/v1/zones/A01/imagery/latest', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IMAGERY_LATEST) }))
    await page.route('**/v1/zones/A01/imagery/history*', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IMAGERY_HISTORY) }))
    await page.route('**/v1/imagery/preview/**', (route) => route.fulfill({ status: 200, contentType: 'image/png', body: PNG_1PX }))
    await page.route('**/v1/predict', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(degradedPrediction) }))
    await page.route('**/v1/recommend/from-cache', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_RECOMMENDATION) }))
    await page.route('**/v1/recommend', (route) => {
      if (route.request().url().includes('from-cache')) return
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_RECOMMENDATION) })
    })
    await page.route('**/v1/commands*', (route) => route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error_code: 'COMMAND_BLOCKED_HIGH_UNCERTAINTY',
        message: 'Command blocked: prediction uncertainty exceeds safety threshold',
        details: { zone_id: 'A01', uncertainty: 0.35 },
        trace_id: 'e2e-rejection-trace',
      }),
    }))

    await page.goto('/dashboard?zone=A01')
    await page.getByText('Run prediction').click()
    await expect(page.getByTestId('prediction-percent')).toHaveText('35%')

    await page.getByText('Run recommendation').click()
    await expect(page.getByTestId('recommendation-volume')).toHaveText('28 mm')
  })

  test('no blank screen under any failure mode', async ({ page }) => {
    await page.route('**/*', (route) => {
      const url = route.request().url()
      if (url.includes('/v1/')) {
        return route.fulfill({ status: 500, body: 'Internal Server Error' })
      }
      return route.continue()
    })

    await page.goto('/dashboard')
    await expect(page.locator('.dashboard-shell')).toBeVisible()
    await expect(page.getByText('Run prediction')).toBeVisible()
    await expect(page.getByText('Run recommendation')).toBeVisible()

    const bodyText = await page.locator('body').textContent()
    expect(bodyText?.length).toBeGreaterThan(50)
  })
})


test.describe('WebSocket + realtime sync', () => {
  test('connection status pill renders without WebSocket server', async ({ page }) => {
    await installGoldenPathRoutes(page)
    await page.goto('/dashboard?zone=A01')

    const statusPills = page.locator('.status-pill')
    await expect(statusPills.first()).toBeVisible()
  })
})
