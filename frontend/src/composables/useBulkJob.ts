import { ref, computed } from 'vue'
import * as svc from '@/services/bulk.service'
import { notify } from '@/utils/notify'
import type { BulkValidationResult } from '@/types'

export type BulkJobState = 'idle' | 'validating' | 'validated' | 'confirming' | 'done' | 'error'

// Extract a clean user-facing message from any thrown error.
// Raw SQLAlchemy / DB stack traces are replaced with a generic message.
function friendlyError(e: unknown, fallback: string): string {
  const raw: string =
    (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (e as { message?: string })?.message ??
    ''
  // Detect technical stack traces — anything with SQLAlchemy, asyncpg, SQL keywords, etc.
  const isTechnical = /sqlalchemy|asyncpg|psycopg|UniqueViolation|INSERT INTO|RETURNING|UUID\(/i.test(raw)
  if (isTechnical || !raw) return fallback
  // Truncate very long messages just in case.
  return raw.length > 200 ? raw.slice(0, 197) + '…' : raw
}

// Singleton refs — shared across the whole app.
const state = ref<BulkJobState>('idle')
const progress = ref(0)          // 0–100
const result = ref<BulkValidationResult | null>(null)
const errorMessage = ref<string | null>(null)
const importSummary = ref<{ importedEntries: number; createdSites: number } | null>(null)

// Callbacks registered by AsbestosRegister to reload after import.
const onImportedCallbacks: Array<() => void> = []

// Signal to open the modal from anywhere (e.g. topbar pill click).
const openModalRequest = ref(0)

// Simulated progress timer handle.
let _timer: ReturnType<typeof setInterval> | null = null

function clearTimer() {
  if (_timer) { clearInterval(_timer); _timer = null }
}

// Crawl progress from current value toward `target` smoothly.
function crawlTo(target: number, intervalMs = 120) {
  clearTimer()
  _timer = setInterval(() => {
    if (progress.value >= target) { clearTimer(); return }
    // Slow down as we approach the target (never quite reaches it until resolved).
    const step = Math.max(0.5, (target - progress.value) * 0.06)
    progress.value = Math.min(target, progress.value + step)
  }, intervalMs)
}

function reset() {
  clearTimer()
  state.value = 'idle'
  progress.value = 0
  result.value = null
  errorMessage.value = null
  importSummary.value = null
}

async function startValidation(file: File) {
  reset()
  state.value = 'validating'
  progress.value = 2
  // Crawl toward 85% — won't reach it until the API resolves.
  crawlTo(85)
  try {
    const data = await svc.validateBulk(file)
    clearTimer()
    progress.value = 100
    result.value = data
    state.value = 'validated'
    notify.success(`Validation complete — ${data.validCount} valid, ${data.errorCount} error(s).`)
  } catch (e: unknown) {
    clearTimer()
    progress.value = 0
    state.value = 'error'
    const msg = friendlyError(e, 'Validation could not be completed. Please try again or contact support.')
    errorMessage.value = msg
    notify.error('Bulk validation failed.')
    console.error('[useBulkJob] validate error:', e)
  }
}

async function confirmImport() {
  if (!result.value) return
  state.value = 'confirming'
  progress.value = 10
  crawlTo(85)
  try {
    const summary = await svc.confirmBulk(result.value.uploadToken)
    clearTimer()
    progress.value = 100
    importSummary.value = summary
    state.value = 'done'
    notify.success(`Import complete — ${summary.importedEntries} entries, ${summary.createdSites} new site(s).`)
    onImportedCallbacks.forEach((cb) => cb())
    // Auto-dismiss the pill after 6 seconds.
    setTimeout(() => { if (state.value === 'done') reset() }, 6000)
  } catch (e: unknown) {
    clearTimer()
    state.value = 'error'
    const msg = friendlyError(e, 'Import could not be completed. Please try again or contact support.')
    errorMessage.value = msg
    notify.error('Bulk import failed.')
    console.error('[useBulkJob] confirm error:', e)
  }
}

function onImported(cb: () => void) {
  if (!onImportedCallbacks.includes(cb)) onImportedCallbacks.push(cb)
}

const isActive = computed(() => state.value !== 'idle')
const isBusy = computed(() => state.value === 'validating' || state.value === 'confirming')

const pillLabel = computed(() => {
  if (state.value === 'validating') return `Validating… ${Math.round(progress.value)}%`
  if (state.value === 'validated') return `Validated — ready to confirm`
  if (state.value === 'confirming') return `Importing… ${Math.round(progress.value)}%`
  if (state.value === 'done') return `Import complete`
  if (state.value === 'error') return `Bulk upload failed`
  return ''
})

const pillClass = computed(() => {
  if (state.value === 'error') return 'bg-rag-red-bg border-rag-red text-rag-red'
  if (state.value === 'done') return 'bg-rag-green-bg border-rag-green text-jl-green-dark'
  if (state.value === 'validated') return 'bg-jl-teal/10 border-jl-teal text-jl-teal-dark'
  return 'bg-slate-100 border-slate-300 text-slate-600'
})

function requestOpenModal() {
  openModalRequest.value++
}

export function useBulkJob() {
  return {
    state,
    progress,
    result,
    errorMessage,
    importSummary,
    isActive,
    isBusy,
    pillLabel,
    pillClass,
    openModalRequest,
    startValidation,
    confirmImport,
    onImported,
    requestOpenModal,
    reset,
  }
}
