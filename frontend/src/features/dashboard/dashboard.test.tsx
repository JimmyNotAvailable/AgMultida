import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { DashboardPage } from './pages/DashboardPage'

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
      <DashboardPage />
    </QueryClientProvider>,
  )
}

test('dashboard shows concrete model results after user actions', async () => {
  renderDashboard()

  fireEvent.click(screen.getByText('Mộc Hoá'))
  fireEvent.click(screen.getByText('Chạy dự đoán'))

  await waitFor(() => expect(screen.getByTestId('prediction-percent').textContent).not.toBe('0%'))
  expect(screen.getAllByText('Xác suất stress').length).toBeGreaterThan(0)
  expect(screen.getByText('Phiên bản mô hình')).toBeTruthy()

  fireEvent.click(screen.getByText('Chạy khuyến nghị'))

  await waitFor(() => expect(screen.getByTestId('recommendation-volume').textContent).toMatch(/^\d+ mm$/))
})

test('dashboard shows imagery controls and metadata', async () => {
  renderDashboard()

  expect(await screen.findByText('Ảnh vùng canh tác')).toBeTruthy()
  expect(screen.getAllByRole('button', { name: 'RGB' }).length).toBeGreaterThan(0)
  expect(screen.getAllByRole('button', { name: 'NDVI' }).length).toBeGreaterThan(0)
  expect(screen.getAllByText('RGB').length).toBeGreaterThan(0)
  expect(screen.getAllByText('NDVI').length).toBeGreaterThan(0)
  expect(screen.getAllByText(/Mây|Cloud/i).length).toBeGreaterThan(0)
  await waitFor(() => expect(screen.getByTestId('imagery-status').textContent).toMatch(/Mới cập nhật|Dữ liệu cũ|Đang tải/))
})


test('dashboard toggles imagery panel mode and visibility', async () => {
  renderDashboard()

  await screen.findByText('Ảnh vùng canh tác')
  fireEvent.click(screen.getAllByRole('button', { name: 'NDVI' })[0])
  fireEvent.click(screen.getByRole('button', { name: 'Ẩn ảnh vệ tinh' }))

  expect(screen.getByRole('button', { name: 'Hiện ảnh vệ tinh' })).toBeTruthy()
})


test('dashboard clears recommendation when selected zone changes', async () => {
  renderDashboard()

  fireEvent.click(screen.getByText('Mỹ Thiện'))
  fireEvent.click(screen.getByText('Chạy dự đoán'))
  await waitFor(() => expect(screen.getByTestId('prediction-percent').textContent).not.toBe('0%'))
  fireEvent.click(screen.getByText('Chạy khuyến nghị'))
  await waitFor(() => expect(screen.getByTestId('recommendation-volume').textContent).toBe('6 mm'))

  fireEvent.click(screen.getByText('Mộc Hoá'))

  expect(screen.getByTestId('recommendation-volume').textContent).toBe('14 mm')
  expect((screen.getByRole('button', { name: 'Thực thi lệnh tưới' }) as HTMLButtonElement).disabled).toBe(true)
})


test('dashboard renders imagery panel state', async () => {
  renderDashboard()

  await waitFor(() => expect(screen.queryByTestId('imagery-preview') ?? screen.queryByTestId('imagery-timeline') ?? screen.queryByTestId('imagery-timeline-loading') ?? screen.queryByTestId('imagery-timeline-error')).toBeTruthy())
})


export {}
