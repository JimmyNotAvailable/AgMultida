import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { ZoneImageryPanel } from './ZoneImageryPanel'
import { ImageryTimeline } from './ImageryTimeline'

const baseScene = {
  zone_id: 'A01',
  scene_id: 'scene-1',
  acquisition_time: new Date().toISOString(),
  cloud_cover: 12,
  rgb_url: '/preview/rgb',
  ndvi_url: '/preview/ndvi',
  source: 'test',
  stale: false,
}

test('fresh cloudy stale badges render from imagery metadata', () => {
  render(<ZoneImageryPanel latest={baseScene} history={null} mode="rgb" isLoading={false} isError={false} onModeChange={() => undefined} />)
  expect(screen.getByTestId('imagery-status').textContent).toBe('Fresh')
})

test('timeline images lazy load', () => {
  render(<ImageryTimeline scenes={[baseScene]} selectedSceneId="scene-1" isLoading={false} isError={false} onSelect={() => undefined} />)
  const timelineImage = screen.getAllByRole('img').find((image) => image.getAttribute('loading') === 'lazy')
  expect(timelineImage?.getAttribute('loading')).toBe('lazy')
})

test('placeholder degraded state visible when latest missing preview', () => {
  render(<ZoneImageryPanel latest={{ ...baseScene, rgb_url: null, ndvi_url: null, stale: true }} history={null} mode="rgb" isLoading={false} isError={false} onModeChange={() => undefined} />)
  expect(screen.getByText('Placeholder imagery')).toBeTruthy()
})
