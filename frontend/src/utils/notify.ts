import { reactive } from 'vue'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: number
  type: ToastType
  message: string
}

// Simple reactive toast store consumed by ToastHost.vue
let seq = 0
export const toasts = reactive<Toast[]>([])

function push(type: ToastType, message: string, ttl = 3500) {
  const id = ++seq
  toasts.push({ id, type, message })
  window.setTimeout(() => dismiss(id), ttl)
}

export function dismiss(id: number) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i !== -1) toasts.splice(i, 1)
}

export const notify = {
  success: (m: string) => push('success', m),
  error: (m: string, ttl = 10000) => push('error', m, ttl),
  info: (m: string) => push('info', m),
  warning: (m: string) => push('warning', m),
}
