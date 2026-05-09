import { fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { expect, test } from 'vitest'
import { WebsitePage } from '../features/website/pages/WebsitePage'
import { AdminPage } from '../features/admin/pages/AdminPage'
import { GuardedRoute } from '../lib/auth/guard'
import { Providers } from './providers'
import { LanguageProvider } from '../lib/i18n/useLanguage'

test('website route renders dashboard CTA', () => {
  const router = createMemoryRouter([{ path: '/', element: <WebsitePage /> }], { initialEntries: ['/'] })

  render(
    <LanguageProvider>
      <RouterProvider router={router} />
    </LanguageProvider>,
  )

  expect(screen.getAllByText('Open Full Dashboard').length).toBeGreaterThan(0)
})

test('website mobile menu exposes section navigation', () => {
  const router = createMemoryRouter([{ path: '/', element: <WebsitePage /> }], { initialEntries: ['/'] })

  render(
    <LanguageProvider>
      <RouterProvider router={router} />
    </LanguageProvider>,
  )

  fireEvent.click(screen.getAllByLabelText('Toggle menu')[0])
  expect(screen.getAllByText('Research').length).toBeGreaterThan(1)
  expect(screen.getAllByText('Access Dashboard').length).toBeGreaterThan(0)
})

test('guarded route blocks when internal routes are disabled', () => {
  const original = import.meta.env.VITE_ENABLE_INTERNAL_ROUTES
  import.meta.env.VITE_ENABLE_INTERNAL_ROUTES = 'false'

  render(
    <GuardedRoute title="Admin route" description="Internal only">
      <div>Admin content</div>
    </GuardedRoute>,
  )

  expect(screen.getByText('Access gated')).toBeTruthy()
  expect(screen.queryByText('Admin content')).toBeNull()
  import.meta.env.VITE_ENABLE_INTERNAL_ROUTES = original
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
