import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { AdminPage } from '../features/admin/pages/AdminPage'
import { DashboardPage } from '../features/dashboard/pages/DashboardPage'
import { ReportsPage } from '../features/reports/pages/ReportsPage'
import { GuardedRoute } from '../lib/auth/guard'
import { Providers } from './providers'

function renderWithQueryClient(element: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
      {element}
    </QueryClientProvider>,
  )
}

test('dashboard route renders new field dashboard as home surface', () => {
  renderWithQueryClient(<DashboardPage />)

  expect(screen.getByRole('heading', { name: /Giám sát/i })).toBeTruthy()
  expect(screen.getByText('Bản đồ & Giám sát')).toBeTruthy()
})

test('dashboard report navigation points to reports route', () => {
  renderWithQueryClient(<DashboardPage />)

  expect(screen.getAllByRole('link', { name: 'Báo cáo' })[0].getAttribute('href')).toBe('/reports')
})

test('reports route renders serious zone report page', () => {
  renderWithQueryClient(
    <MemoryRouter>
      <ReportsPage />
    </MemoryRouter>,
  )

  expect(screen.getByRole('heading', { name: /Báo cáo/i })).toBeTruthy()
  expect(screen.getByTestId('report-summary')).toBeTruthy()
})

test('guarded route redirects to login when token is missing', () => {
  const originalToken = import.meta.env.VITE_DEV_ACCESS_TOKEN
  import.meta.env.VITE_DEV_ACCESS_TOKEN = ''
  window.localStorage.removeItem('agmultida.accessToken')

  render(
    <MemoryRouter initialEntries={['/admin']}>
      <GuardedRoute>
        <div>Admin content</div>
      </GuardedRoute>
    </MemoryRouter>,
  )

  expect(screen.queryByText('Admin content')).toBeNull()
  import.meta.env.VITE_DEV_ACCESS_TOKEN = originalToken
})

test('login page renders route copy', async () => {
  const originalToken = import.meta.env.VITE_DEV_ACCESS_TOKEN
  import.meta.env.VITE_DEV_ACCESS_TOKEN = ''
  window.localStorage.removeItem('agmultida.accessToken')

  const module = await import('../features/auth/pages/LoginPage')
  render(
    <MemoryRouter>
      <module.LoginPage />
    </MemoryRouter>,
  )

  expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeTruthy()
  import.meta.env.VITE_DEV_ACCESS_TOKEN = originalToken
})

test('admin page renders when internal routes are enabled', () => {
  const original = import.meta.env.VITE_ENABLE_INTERNAL_ROUTES
  import.meta.env.VITE_ENABLE_INTERNAL_ROUTES = 'true'
  import.meta.env.VITE_DEV_ACCESS_TOKEN = 'test-token'

  render(
    <Providers>
      <AdminPage />
    </Providers>,
  )

  expect(screen.getByText('Gateway operations surface')).toBeTruthy()
  import.meta.env.VITE_ENABLE_INTERNAL_ROUTES = original
})
