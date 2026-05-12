import { createBrowserRouter } from 'react-router-dom'
import { AdminPage } from '../features/admin/pages/AdminPage'
import { LoginPage } from '../features/auth/pages/LoginPage'
import { DashboardPage } from '../features/dashboard/pages/DashboardPage'
import { ReportsPage } from '../features/reports/pages/ReportsPage'
import { GuardedRoute, isInternalRoutesEnabled } from '../lib/auth/guard'

const routes = [
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <GuardedRoute>
        <DashboardPage />
      </GuardedRoute>
    ),
  },
  {
    path: '/dashboard',
    element: (
      <GuardedRoute>
        <DashboardPage />
      </GuardedRoute>
    ),
  },
  {
    path: '/reports',
    element: (
      <GuardedRoute>
        <ReportsPage />
      </GuardedRoute>
    ),
  },
]

if (isInternalRoutesEnabled()) {
  routes.push({
    path: '/admin',
    element: (
      <GuardedRoute>
        <AdminPage />
      </GuardedRoute>
    ),
  })
}

export const router = createBrowserRouter(routes, {
  future: {
    v7_relativeSplatPath: true,
  },
})
