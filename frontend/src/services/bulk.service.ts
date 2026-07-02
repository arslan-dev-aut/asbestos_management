import { api, API_BASE, USE_MOCK, mockDelay, uid } from './api'
import type { BulkValidationResult, BulkUploadRow } from '@/types'

// Template column order — must match the backend xlsx exactly.
export const BULK_TEMPLATE_COLUMNS = [
  'Customer', 'Customer ID', 'Site Name', 'Site ID', 'Building',
  'Room/Location', 'Asset', 'ACM Type', 'Condition', 'Risk Score', 'Notes',
]

export async function downloadTemplate(): Promise<void> {
  if (USE_MOCK) {
    const csv = BULK_TEMPLATE_COLUMNS.join(',') + '\n'
    triggerCsvDownload(csv, 'asbestos-bulk-template.csv')
    return mockDelay(undefined)
  }
  const res = await api.get(`${API_BASE}/register/bulk-upload/template`, { responseType: 'blob' })
  triggerBlobDownload(res.data, 'asbestos-bulk-template.xlsx')
}

export async function validateBulk(_file: File): Promise<BulkValidationResult> {
  if (USE_MOCK) {
    // Deterministic sample preview so the UI can be built without a parser.
    const rows: BulkUploadRow[] = [
      { rowIndex: 1, status: 'VALID', errorDetail: null, customerName: 'KFC', siteName: 'KFC - Cardiff Queen St', building: 'Main Building', roomLocation: 'Cellar', asset: null, acmType: 'Pipe Lagging', condition: 'Good', riskScore: 'Low', notes: null },
      { rowIndex: 2, status: 'VALID', errorDetail: null, customerName: 'KFC', siteName: 'KFC - Cardiff Queen St', building: 'Kitchen Block', roomLocation: 'Extract duct', asset: null, acmType: 'Insulation Board', condition: 'Low Damage', riskScore: 'Medium', notes: 'Encapsulated' },
      { rowIndex: 3, status: 'ERROR', errorDetail: 'ACM Type not found', customerName: 'KFC', siteName: 'KFC - Manchester Arndale', building: 'Main Building', roomLocation: 'Loft', asset: null, acmType: 'Vermiculite', condition: 'Good', riskScore: 'Low', notes: null },
      { rowIndex: 4, status: 'ERROR', errorDetail: 'Site not found in system', customerName: 'KFC', siteName: 'KFC - Unknown Town', building: 'Main Building', roomLocation: 'Roof', asset: null, acmType: 'Floor Tiles', condition: 'Good', riskScore: 'Low', notes: null },
    ]
    return mockDelay({
      rows,
      validCount: rows.filter((r) => r.status === 'VALID').length,
      errorCount: rows.filter((r) => r.status === 'ERROR').length,
      sitesToCreate: ['KFC - Cardiff Queen St'],
      uploadToken: uid('upload'),
    })
  }
  const fd = new FormData()
  fd.append('file', _file)
  const { data } = await api.post(`${API_BASE}/register/bulk-upload/validate`, fd)
  return data
}

export async function confirmBulk(uploadToken: string): Promise<{ importedEntries: number; createdSites: number }> {
  if (USE_MOCK) return mockDelay({ importedEntries: 2, createdSites: 1 })
  const { data } = await api.post(`${API_BASE}/register/bulk-upload/confirm`, { uploadToken })
  if (data.success === false) throw new Error(data.message ?? 'Import failed on the server.')
  return { importedEntries: data.importedEntries, createdSites: data.createdSites }
}

// ─── Export ─────────────────────────────────────────────────────────────────
// Export respects the currently-applied register filters (search, customers,
// risk levels) — same param names as the register list endpoint.
export interface ExportFilters {
  search?: string
  customerIds?: string[]
  riskLevels?: string[]
}

export async function exportRegister(filters: ExportFilters = {}): Promise<void> {
  if (USE_MOCK) {
    const header = ['Customer', 'Customer ID', 'Site Name', 'Site ID', 'Building', 'Room/Location', 'Asset', 'ACM Type', 'Condition', 'Risk Score', 'Status', 'Last Updated', 'Updated By']
    triggerCsvDownload(header.join(',') + '\n', 'asbestos-register-export.csv')
    return mockDelay(undefined)
  }
  const params = new URLSearchParams()
  params.set('format', 'xlsx') // match the .xlsx filename we save as
  if (filters.search?.trim()) params.set('search', filters.search.trim())
  ;(filters.customerIds ?? []).forEach((c) => params.append('customerIds', c))
  ;(filters.riskLevels ?? []).forEach((r) => params.append('riskLevel', r))
  const res = await api.get(`${API_BASE}/register/export`, { params, responseType: 'blob' })
  triggerBlobDownload(res.data, 'asbestos-register-export.xlsx')
}

function triggerCsvDownload(csv: string, filename: string) {
  triggerBlobDownload(new Blob([csv], { type: 'text/csv' }), filename)
}
function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
