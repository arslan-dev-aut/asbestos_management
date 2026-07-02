// Date formatting helpers (UK format, matching the prototype: "28 May 2026")
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${formatDate(iso)}, ${hh}:${mm}`
}

// Convert a JS Date / yyyy-mm-dd input value to ISO date string (date only)
export function toIsoDate(value: string): string {
  // value is already yyyy-mm-dd from <input type=date> — return as-is (backend expects date not datetime)
  return value ?? ''
}
