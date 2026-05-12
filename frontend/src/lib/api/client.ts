import { refreshSession } from '../auth/api'
import { clearAuthTokens, getAccessToken, getRefreshToken } from '../auth/token'
import { ApiError, type ApiErrorBody } from './types'

const DEFAULT_API_BASE_URL = 'http://localhost:8000'
let refreshInFlight: Promise<string | null> | null = null

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
}

export function getWsUrl(): string {
  const configured = import.meta.env.VITE_WS_URL
  if (configured) {
    return configured
  }

  const url = new URL(getApiBaseUrl())
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/updates'
  return url.toString()
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await performRequest(path, init)

  if (response.status === 401 && shouldAttachAuth(path)) {
    const refreshedToken = await refreshAccessToken()
    if (refreshedToken) {
      const retryResponse = await performRequest(path, init, refreshedToken)
      return parseApiResponse<T>(retryResponse)
    }

    clearAuthTokens()
    throw new ApiError('Authentication required', 401, null)
  }

  return parseApiResponse<T>(response)
}

async function performRequest(path: string, init: RequestInit, overrideToken?: string): Promise<Response> {
  const token = shouldAttachAuth(path) ? (overrideToken ?? getAccessToken()) : null
  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  })
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    return null
  }

  if (!refreshInFlight) {
    refreshInFlight = refreshSession(refreshToken)
      .then((session) => session.access_token)
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null
      })
  }

  return refreshInFlight
}

async function parseApiResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  const body = parseJsonSafely(text)

  if (!response.ok) {
    const errorBody = isApiErrorBody(body) ? body : null
    const message = errorBody?.message ? 'Request failed' : text ? 'Request failed' : `Request failed with ${response.status}`
    throw new ApiError(message, response.status, errorBody)
  }

  if (text && body === null) {
    throw new ApiError('Response was not valid JSON', response.status, null)
  }

  return body as T
}

function parseJsonSafely(text: string): unknown | null {
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === 'object' && value !== null
}

function shouldAttachAuth(path: string): boolean {
  return path.startsWith('/v1/zones') || path.startsWith('/v1/alerts') || path === '/v1/predict' || path.startsWith('/v1/recommend') || path === '/v1/telemetry' || path === '/v1/commands' || path === '/v1/auth/me'
}

export function resetApiClientStateForTests(): void {
  refreshInFlight = null
}
