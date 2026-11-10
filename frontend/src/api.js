const API_ROOT = import.meta.env.VITE_API_URL || '/api'

export async function api(path, { token, ...options } = {}) {
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers })
  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const error = new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return data
}

export function jsonBody(value) {
  return JSON.stringify(value)
}

export function userFromToken(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return { id: payload.sub, email: payload.email }
  } catch {
    return { id: null, email: '' }
  }
}
