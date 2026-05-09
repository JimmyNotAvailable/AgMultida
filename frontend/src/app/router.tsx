import { createBrowserRouter } from 'react-router-dom'
import { AdminPage } from '../features/admin/pages/AdminPage'
import { DashboardPage } from '../features/dashboard/pages/DashboardPage'
import { WebsitePage } from '../features/website/pages/WebsitePage'
import { isInternalRoutesEnabled } from '../lib/auth/guard'

const routes = [
  {
    path: '/',
    element: <WebsitePage />,
  },
  {
    path: '/dashboard',
    element: <DashboardPage />,
  },
]

if (isInternalRoutesEnabled()) {
  routes.push({
    path: '/admin',
    element: <AdminPage />,
  })
}

export const router = createBrowserRouter(routes)
