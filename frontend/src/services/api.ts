import axios from 'axios'

// Single swap point: while the backend is being built, USE_MOCK stays true and
// every service returns local mock data. When the backend is ready, flip this
// to false (or set VITE_USE_MOCK=false) — views/components do not change.
export const USE_MOCK =
  (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false'

export const API_BASE = '/api/v1/asbestos'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  timeout: 300000,
})

// Resolve tenant ID and access token.
// VITE_USE_HARDCODED_AUTH=true  → use env vars (local dev / testing)
// VITE_USE_HARDCODED_AUTH=false → read from parent Joblogic sessionStorage (iframe / production)
function resolveAuth(): { tenantId: string; userId: string } {
  const useHardcoded = (import.meta.env.VITE_USE_HARDCODED_AUTH ?? 'true') !== 'false'

  if (useHardcoded) {
    return {
      tenantId: import.meta.env.VITE_TENANT_ID ?? '',
      userId: import.meta.env.VITE_USER_ID ?? '',
    }
  }

  // iframe mode: read from parent Joblogic sessionStorage (same origin).
  const tenantId = sessionStorage.getItem('temporary.TenantId') ?? ''
  const userId = sessionStorage.getItem('temporary.UserId') ?? ''

  // OIDC key varies by environment (uat / go / etc) so scan by prefix + domain.
  // const oidcKey = Object.keys(sessionStorage).find(
  //   (k) => k.startsWith('oidc.user:') && k.includes('joblogic.com'),
  // )
  // let accessToken = ''
  // if (oidcKey) {
  //   try {
  //     const parsed = JSON.parse(sessionStorage.getItem(oidcKey) ?? '{}')
  //     accessToken = parsed.access_token ?? ''
  //   } catch {
  //     // malformed entry — leave token blank
  //   }
  // }

  return { tenantId, userId }
}

api.interceptors.request.use((config) => {
  const { tenantId, userId } = resolveAuth()
  if (tenantId) config.headers['X-Tenant-Id'] = tenantId
  if (tenantId) config.headers['X-User-Id'] = userId
  // Bypass ngrok's browser-warning interstitial on direct calls.
  config.headers['ngrok-skip-browser-warning'] = 'true'
  return config
})

// Simulated network latency so mock UX matches real async behaviour.
export function mockDelay<T>(data: T, ms = 250): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms))
}

// Lightweight UUID for mock-created records.
export function uid(prefix = 'id'): string {
  return `${prefix}-${Math.floor(performance.now() * 1000).toString(36)}-${Math.floor(performance.now() % 1).toString(36)}${(globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2))}`
}