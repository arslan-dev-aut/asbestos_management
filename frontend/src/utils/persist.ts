// Mock-state persistence. In the mock build, services mutate in-memory arrays.
// Because the QR page and Customer Portal preview open in a SEPARATE browser
// tab (window.open), that tab starts with its own fresh module state and would
// not see changes made in the admin tab. Persisting to localStorage gives every
// tab a single shared source of truth so mutations reflect everywhere.
//
// When the real backend is wired (USE_MOCK=false) none of this runs.

export function loadState<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function saveState(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore quota / serialization errors in mock build */
  }
}
