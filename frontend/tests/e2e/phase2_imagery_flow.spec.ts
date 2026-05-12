import { expect, test } from '@playwright/test'

test('phase2 imagery flow shows latest scene, preview proxy, timeline, and stale state', async ({ page }) => {
  await page.route('**/v1/zones/A01/imagery/latest', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        zone_id: 'A01',
        scene_id: 'S2A_A01_20260508',
        acquisition_time: '2026-05-08T08:42:00Z',
        cloud_cover: 8.5,
        rgb_url: '/v1/imagery/preview/S2A_A01_20260508?mode=rgb',
        ndvi_url: '/v1/imagery/preview/S2A_A01_20260508?mode=ndvi',
        source: 'sentinel-2-l2a',
        stale: false,
      }),
    })
  })

  await page.route('**/v1/zones/A01/imagery/history?limit=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        trace_id: 'phase2-imagery-history',
        zone_id: 'A01',
        scenes: [
          {
            zone_id: 'A01',
            scene_id: 'S2A_A01_20260508',
            acquisition_time: '2026-05-08T08:42:00Z',
            cloud_cover: 8.5,
            rgb_url: '/v1/imagery/preview/S2A_A01_20260508?mode=rgb',
            ndvi_url: '/v1/imagery/preview/S2A_A01_20260508?mode=ndvi',
            source: 'sentinel-2-l2a',
            stale: false,
          },
          {
            zone_id: 'A01',
            scene_id: 'S2A_A01_20260501',
            acquisition_time: '2026-05-01T08:42:00Z',
            cloud_cover: 14.2,
            rgb_url: '/v1/imagery/preview/S2A_A01_20260501?mode=rgb',
            ndvi_url: '/v1/imagery/preview/S2A_A01_20260501?mode=ndvi',
            source: 'sentinel-2-l2a',
            stale: true,
          },
        ],
      }),
    })
  })

  await page.route('**/v1/imagery/preview/**', async (route) => {
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: png,
      headers: {
        'Cache-Control': 'private, max-age=86400',
        'X-Preview-Source': 'rendered',
      },
    })
  })

  await page.goto('/dashboard?zone=A01')

  await expect(page.getByTestId('imagery-panel')).toBeVisible()
  await expect(page.getByTestId('imagery-status')).toHaveText('Fresh')
  await expect(page.getByTestId('imagery-preview')).toHaveAttribute('src', /S2A_A01_20260508\?mode=rgb/)
  await expect(page.getByTestId('imagery-timeline')).toBeVisible()
  await expect(page.getByTestId('imagery-timeline-scene')).toHaveCount(2)

  await page.getByRole('button', { name: 'NDVI' }).click()
  await expect(page.getByTestId('imagery-preview')).toHaveAttribute('src', /S2A_A01_20260508\?mode=ndvi/)

  await page.getByTestId('imagery-timeline-scene').nth(1).click()
  await expect(page.getByTestId('imagery-status')).toHaveText('Stale')
  await expect(page.getByTestId('imagery-stale-copy')).toBeVisible()
  await expect(page.getByTestId('imagery-preview')).toHaveAttribute('src', /S2A_A01_20260501\?mode=ndvi/)
})
