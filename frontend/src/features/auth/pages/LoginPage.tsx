import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { login } from '../../../lib/auth/api'
import { hasAccessToken } from '../../../lib/auth/token'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (hasAccessToken()) {
    return <Navigate to="/dashboard" replace />
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(username, password)
      const target = typeof location.state === 'object' && location.state !== null && 'from' in location.state
        ? String(location.state.from)
        : '/dashboard'
      navigate(target, { replace: true })
    } catch {
      setError('Tên đăng nhập hoặc mật khẩu không đúng.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="status-pill ok">AgMultida Admin</div>
        <h1>Đăng nhập</h1>
        <p className="section-copy">Dùng tài khoản quản trị để truy cập dashboard và API nội bộ.</p>
        <label>
          <span>Tên đăng nhập</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          <span>Mật khẩu</span>
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" />
        </label>
        {error ? <p role="alert" className="login-error">{error}</p> : null}
        <button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
      </form>
    </main>
  )
}
