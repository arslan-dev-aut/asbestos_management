import { api, API_BASE, USE_MOCK, mockDelay, uid } from './api'
import * as reg from '@/mocks/register'
import { ampExpiryRag } from '@/utils/rag'
import { viewFile, downloadFile } from '@/utils/fileStore'
import type { SiteDocument, DocType } from '@/types'

/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
function mapDoc(d: any): SiteDocument {
  return {
    id: d.id,
    asbestosSiteId: d.asbestosSiteId,
    docType: d.docType,
    fileName: d.fileName,
    fileUrl: d.fileUrl ?? null,
    downloadUrl: d.downloadUrl ?? null,
    ampExpiryDate: d.ampExpiryDate,
    ampExpiryRag: d.ampExpiryRag ?? null,
    isCurrentAmp: d.isCurrentAmp,
    uploadedAt: d.uploadedAt,
    uploadedById: d.uploadedBy,
    uploadedByName: d.uploadedByName,
  }
}

export interface DocumentsPage {
  items: SiteDocument[]
  totalCount: number
  page: number
  pageSize: number
}

// Server-side paginated documents, newest-first within the page.
export async function getDocumentsPaged(
  asbestosSiteId: string,
  opts: { page?: number; pageSize?: number } = {},
): Promise<DocumentsPage> {
  const page = opts.page ?? 0
  const pageSize = opts.pageSize ?? 10
  if (USE_MOCK) {
    const all = reg.documents
      .filter((d) => d.asbestosSiteId === asbestosSiteId)
      .map((d) => ({ ...d, ampExpiryRag: d.docType === 'AMP' ? ampExpiryRag(d.ampExpiryDate) : null }))
      .sort((a, b) => (b.uploadedAt > a.uploadedAt ? 1 : -1))
    const start = page * pageSize
    return mockDelay({ items: all.slice(start, start + pageSize), totalCount: all.length, page, pageSize })
  }
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/documents`, {
    params: { page, pageSize },
  })
  // Newest-first within the page (backend ideally orders by uploadedAt desc).
  const items = (data.documents ?? [])
    .map(mapDoc)
    .sort((a: SiteDocument, b: SiteDocument) => (b.uploadedAt ?? '').localeCompare(a.uploadedAt ?? ''))
  return { items, totalCount: data.total ?? data.totalCount ?? items.length, page, pageSize }
}

export async function getDocuments(asbestosSiteId: string): Promise<SiteDocument[]> {
  if (USE_MOCK) {
    const docs = reg.documents
      .filter((d) => d.asbestosSiteId === asbestosSiteId)
      .map((d) => ({ ...d, ampExpiryRag: d.docType === 'AMP' ? ampExpiryRag(d.ampExpiryDate) : null }))
      // current AMP first, then superseded AMPs newest-first, then others
      .sort((a, b) => (b.uploadedAt > a.uploadedAt ? 1 : -1))
    return mockDelay(docs)
  }
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/documents`, {
    params: { page: 0, pageSize: 50 },
  })
  return (data.documents ?? []).map(mapDoc)
}

export interface UploadDocInput {
  fileName: string
  docType: DocType
  ampExpiryDate: string | null // required when docType === 'AMP'
  file?: File // real File object for the real-API path; omitted in mock
}

// Upload MANY documents in a SINGLE multipart request — the endpoint accepts
// repeatable `files` + a `documentsMetadata` JSON array (fileIndex maps each
// metadata entry to its file). One round-trip; backend handles AMP-supersede
// atomically. Preferred over calling uploadDocument() in a loop.
export async function uploadDocuments(asbestosSiteId: string, inputs: UploadDocInput[]): Promise<SiteDocument[]> {
  if (USE_MOCK) {
    const out: SiteDocument[] = []
    for (const input of inputs) out.push(await uploadDocument(asbestosSiteId, input))
    return out
  }
  if (inputs.some((i) => !i.file)) throw new Error('File data unavailable — please re-select the file(s).')
  const form = new FormData()
  const metadata = inputs.map((input, fileIndex) => {
    form.append('files', input.file!, input.fileName)
    const meta: Record<string, unknown> = { fileIndex, docType: input.docType }
    if (input.docType === 'AMP') meta.ampExpiryDate = input.ampExpiryDate
    return meta
  })
  form.append('documentsMetadata', JSON.stringify(metadata))
  const { data } = await api.post(`${API_BASE}/register/${asbestosSiteId}/documents`, form, { timeout: 120000 })
  return (data.documents ?? []).map(mapDoc)
}

export async function uploadDocument(asbestosSiteId: string, input: UploadDocInput): Promise<SiteDocument> {
  if (USE_MOCK) {
    const now = new Date().toISOString()
    // AMP supersede: mark all prior AMPs not-current.
    if (input.docType === 'AMP') {
      const prior = reg.documents.find((d) => d.asbestosSiteId === asbestosSiteId && d.docType === 'AMP' && d.isCurrentAmp)
      reg.documents
        .filter((d) => d.asbestosSiteId === asbestosSiteId && d.docType === 'AMP')
        .forEach((d) => (d.isCurrentAmp = false))
      if (prior) {
        reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'AMP_REPLACED', summary: 'AMP replaced', details: { previousAmpName: prior.fileName, previousExpiryDate: prior.ampExpiryDate, newAmpName: input.fileName, newExpiryDate: input.ampExpiryDate }, occurredAt: now })
      }
    }
    const doc: SiteDocument = {
      id: uid('doc'), asbestosSiteId, docType: input.docType, fileName: input.fileName,
      fileKey: null,
      ampExpiryDate: input.docType === 'AMP' ? input.ampExpiryDate : null,
      ampExpiryRag: input.docType === 'AMP' ? ampExpiryRag(input.ampExpiryDate) : null,
      isCurrentAmp: input.docType === 'AMP',
      uploadedAt: now, uploadedById: 'user-sarah', uploadedByName: 'Sarah Jones',
    }
    reg.documents.push(doc)
    reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_DOCUMENT_UPLOADED', summary: 'Site document uploaded', details: { documentName: input.fileName, documentType: input.docType, fileSize: '— KB' }, occurredAt: now })
    reg.commit()
    return mockDelay(doc)
  }
  // Real API: multipart/form-data with files[] + documentsMetadata JSON string.
  if (!input.file) throw new Error('File data unavailable — please re-select the file.')
  const form = new FormData()
  form.append('files', input.file, input.fileName)
  const meta: Record<string, unknown> = { fileIndex: 0, docType: input.docType }
  if (input.docType === 'AMP') meta.ampExpiryDate = input.ampExpiryDate
  form.append('documentsMetadata', JSON.stringify([meta]))
  const { data } = await api.post(`${API_BASE}/register/${asbestosSiteId}/documents`, form, { timeout: 120000 })
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  const d: any = (data.documents ?? [])[0] ?? data.document ?? {}
  return {
    id: d.id, asbestosSiteId: d.asbestosSiteId, docType: d.docType, fileName: d.fileName,
    fileUrl: d.fileUrl ?? null, ampExpiryDate: d.ampExpiryDate, ampExpiryRag: d.ampExpiryRag ?? null,
    isCurrentAmp: d.isCurrentAmp, uploadedAt: d.uploadedAt, uploadedById: d.uploadedBy, uploadedByName: d.uploadedByName,
  }
}

export async function removeDocument(asbestosSiteId: string, documentId: string): Promise<void> {
  if (USE_MOCK) {
    const i = reg.documents.findIndex((d) => d.id === documentId)
    if (i !== -1) {
      const doc = reg.documents[i]
      reg.documents.splice(i, 1)
      reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_DOCUMENT_REMOVED', summary: 'Site document removed', details: { documentName: doc.fileName, documentType: doc.docType }, occurredAt: new Date().toISOString() })
      reg.commit()
    }
    return mockDelay(undefined)
  }
  await api.delete(`${API_BASE}/register/${asbestosSiteId}/documents/${documentId}`)
}

// Route the download through the local Vite dev proxy (/blob-download) so
// Node.js fetches the blob server-side and adds Content-Disposition: attachment.
// This avoids the browser CORS block on direct cross-origin fetch() calls and
// forces a save-to-disk regardless of the blob storage server's own headers.
//
// We fetch the proxied blob and AWAIT it before triggering the save, so callers
// that show a loading indicator while awaiting downloadDocument()/downloadAttachment()
// keep it visible for the real duration of the download (not just the click).
async function triggerDownload(presignedUrl: string, fileName: string): Promise<void> {
  const proxy = `/blob-download?url=${encodeURIComponent(presignedUrl)}&name=${encodeURIComponent(fileName)}`
  const res = await fetch(proxy)
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// Returns a presigned URL for a site document.
async function resolveDocUrl(asbestosSiteId: string, documentId: string): Promise<string> {
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/documents/${documentId}/download`)
  return data.url
}

// Returns a presigned URL for an ACM entry attachment.
async function resolveAttachmentUrl(asbestosSiteId: string, acmEntryId: string, attachmentId: string): Promise<string> {
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/acm/${acmEntryId}/attachments/${attachmentId}/download`)
  return data.url
}

// View opens in a new tab; Download saves the file.
// Uses downloadUrl from the list response directly — no extra round-trip needed.
export async function viewDocument(asbestosSiteId: string, doc: SiteDocument): Promise<void> {
  if (USE_MOCK) return viewFile(doc.fileName, doc.fileKey)
  const url = doc.downloadUrl ?? await resolveDocUrl(asbestosSiteId, doc.id)
  window.open(url, '_blank')
}
export async function downloadDocument(asbestosSiteId: string, doc: SiteDocument): Promise<void> {
  if (USE_MOCK) return downloadFile(doc.fileName, doc.fileKey)
  const url = doc.downloadUrl ?? await resolveDocUrl(asbestosSiteId, doc.id)
  await triggerDownload(url, doc.fileName)
}

export async function viewAttachment(
  asbestosSiteId: string, acmEntryId: string, attachmentId: string,
  _fileName: string, downloadUrl?: string | null,
): Promise<void> {
  const url = downloadUrl ?? await resolveAttachmentUrl(asbestosSiteId, acmEntryId, attachmentId)
  window.open(url, '_blank')
}
export async function downloadAttachment(
  asbestosSiteId: string, acmEntryId: string, attachmentId: string,
  fileName: string, downloadUrl?: string | null,
): Promise<void> {
  const url = downloadUrl ?? await resolveAttachmentUrl(asbestosSiteId, acmEntryId, attachmentId)
  await triggerDownload(url, fileName)
}
