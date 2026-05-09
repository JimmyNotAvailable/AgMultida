import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { DashboardPage } from './pages/DashboardPage'
import { LanguageProvider } from '../../lib/i18n/useLanguage'

afterEach(() => {
  cleanup()
})

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <DashboardPage />
      </LanguageProvider>
    </QueryClientProvider>,
  )
}

test('dashboard shows concrete model results after user actions', async () => {
  renderDashboard()

  fireEvent.click(screen.getByText('An Giang A03'))
  fireEvent.click(screen.getByText('Run prediction'))

  await waitFor(() => expect(screen.getByTestId('prediction-percent').textContent).toBe('78%'))
  expect(screen.getAllByText('Stress probability').length).toBeGreaterThan(0)
  expect(screen.getByText('Model version')).toBeTruthy()

  fireEvent.click(screen.getByText('Run recommendation'))

  await waitFor(() => expect(screen.getByTestId('recommendation-volume').textContent).toBe('28 mm'))
  expect(screen.getAllByText('critical_stress_low_moisture').length).toBeGreaterThan(0)
})

test('dashboard shows imagery controls and metadata', async () => {
  renderDashboard()

  expect(await screen.findByText('Zone imagery')).toBeTruthy()
  expect(screen.getByText('Satellite layer')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'RGB' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'NDVI' })).toBeTruthy()
  expect(screen.getAllByText('Cloud cover').length).toBeGreaterThan(0)
  await waitFor(() => expect(screen.getByTestId('imagery-status').textContent).toMatch(/Fresh|Stale/))
})


test('dashboard toggles imagery panel mode and visibility', async () => {
  renderDashboard()

  fireEvent.click(await screen.findByRole('button', { name: 'NDVI' }))
  fireEvent.click(screen.getByRole('button', { name: 'Hide imagery' }))

  expect(screen.getByRole('button', { name: 'Show imagery' })).toBeTruthy()
})


test('dashboard renders imagery timeline entries', async () => {
  renderDashboard()

  await waitFor(() => expect(screen.getByTestId('imagery-timeline')).toBeTruthy())
  expect(screen.getAllByTestId('imagery-timeline-scene').length).toBeGreaterThan(0)
  expect(screen.getByTestId('imagery-preview')).toBeTruthy()
})


export {}
