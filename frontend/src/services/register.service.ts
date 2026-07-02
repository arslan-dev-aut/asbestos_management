import { api, API_BASE, USE_MOCK, mockDelay, uid } from './api'
import * as reg from '@/mocks/register'
import * as look from '@/mocks/lookups'
import { ampExpiryRag, highestRisk } from '@/utils/rag'
import { PAGE_SIZE, conditionLabel, riskLabel } from '@/utils/const'
import type {
  SiteListItem, SiteDetail, SiteDocument, AcmEntry, AcmAttachment, Paginated, RiskScore, LookupOption,
} from '@/types'

export interface RegisterQuery {
  search?: string
  customerIds?: string[]
  siteIds?: string[]
  riskLevels?: (RiskScore | 'NONE')[]
  sortBy?: 'ampExpiry' | 'lastUpdated'
  sortDir?: 'asc' | 'desc'
  pageIndex?: number
  pageSize?: number
}

// ─── Real-API response mappers ──────────────────────────────────────────────
// The backend returns `id`/`updatedBy`; the frontend models use
// `asbestosSiteId`/`updatedById`. These translate between the two.
/* eslint-disable @typescript-eslint/no-explicit-any */
function mapListItem(s: any): SiteListItem {
  return {
    asbestosSiteId: s.id,
    customerId: s.customerId,
    customerName: s.customerName,
    siteId: s.siteId,
    siteName: s.siteName,
    totalAcm: s.totalAcm,
    activeAcm: s.activeAcm,
    highestRisk: s.highestRisk,
    ampExpiryDate: s.ampExpiryDate,
    ampExpiryRag: s.ampExpiryRag ?? 'NONE',
    lastUpdated: s.lastUpdated,
    updatedById: s.updatedBy,
    updatedByName: s.updatedByName,
  }
}

function mapSiteDetail(s: any): SiteDetail {
  return {
    asbestosSiteId: s.id,
    customerId: s.customerId,
    customerName: s.customerName,
    siteId: s.siteId,
    siteName: s.siteName,
    createdAt: s.createdAt,
    createdById: s.createdBy,
    updatedAt: s.updatedAt,
    updatedById: s.updatedBy,
  }
}

function mapAttachment(a: any): AcmAttachment {
  return {
    id: a.id,
    fileName: a.fileName,
    downloadUrl: a.downloadUrl ?? null,
    fileUrl: a.fileUrl ?? null,
  }
}

function mapAcm(e: any): AcmEntry {
  return {
    id: e.id,
    asbestosSiteId: e.asbestosSiteId ?? '',
    buildingTypeId: e.buildingTypeId ?? '',
    buildingTypeName: e.building ?? e.buildingTypeName ?? '',
    roomLocation: e.roomLocation,
    assetId: e.assetId ?? null,
    assetName: e.assetName ?? null,
    assetDiscrepancy: e.assetDiscrepancy ?? false,
    acmTypeId: e.acmTypeId ?? '',
    acmTypeName: e.acmType ?? e.acmTypeName ?? '',
    condition: e.condition,
    riskScore: e.riskScore,
    notes: e.notes ?? null,
    status: e.status,
    attachments: (e.attachments ?? []).map(mapAttachment),
    updatedAt: e.updatedAt ?? undefined,
    updatedById: e.updatedBy ?? undefined,
    updatedByName: e.updatedByName ?? undefined,
  }
}

function mapDocument(d: any): SiteDocument {
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
/* eslint-enable @typescript-eslint/no-explicit-any */

// Build a computed SiteListItem from a raw site row (resolves names + RAG).
function toListItem(s: reg.RawSite): SiteListItem {
  const entries = reg.acmEntries.filter((e) => e.asbestosSiteId === s.asbestosSiteId)
  const active = entries.filter((e) => e.status === 'ACTIVE')
  const currentAmp = reg.documents.find((d) => d.asbestosSiteId === s.asbestosSiteId && d.docType === 'AMP' && d.isCurrentAmp)
  const hr = highestRisk(active.map((e) => e.riskScore))
  return {
    asbestosSiteId: s.asbestosSiteId,
    customerId: s.customerId,
    customerName: look.customerName(s.customerId),
    siteId: s.siteId,
    siteName: look.siteName(s.siteId),
    totalAcm: entries.length,
    activeAcm: active.length,
    highestRisk: hr,
    ampExpiryDate: currentAmp?.ampExpiryDate ?? null,
    ampExpiryRag: ampExpiryRag(currentAmp?.ampExpiryDate ?? null),
    lastUpdated: s.updatedAt,
    updatedById: s.updatedById,
    updatedByName: look.userName(s.updatedById),
  }
}

export async function getRegister(q: RegisterQuery = {}): Promise<Paginated<SiteListItem>> {
  if (USE_MOCK) {
    let items = reg.sites.map(toListItem)

    // Search resolves against resolved names (mirrors MainSubSys ID resolution).
    if (q.search?.trim()) {
      const term = q.search.toLowerCase()
      items = items.filter((i) => i.siteName.toLowerCase().includes(term) || i.customerName.toLowerCase().includes(term))
    }
    if (q.customerIds?.length) items = items.filter((i) => q.customerIds!.includes(i.customerId))
    if (q.siteIds?.length) items = items.filter((i) => q.siteIds!.includes(i.siteId))
    if (q.riskLevels?.length) items = items.filter((i) => q.riskLevels!.includes(i.highestRisk))

    if (q.sortBy === 'ampExpiry') {
      const dir = q.sortDir === 'desc' ? -1 : 1
      items.sort((a, b) => ((a.ampExpiryDate ?? '') > (b.ampExpiryDate ?? '') ? dir : -dir))
    }

    const totalCount = items.length
    const pageIndex = q.pageIndex ?? 0
    const pageSize = q.pageSize ?? PAGE_SIZE
    const start = pageIndex * pageSize
    return mockDelay({ items: items.slice(start, start + pageSize), totalCount, pageIndex, pageSize })
  }
  // Build repeated query params (FastAPI expects ?customerIds=a&customerIds=b)
  // and the singular `riskLevel` param name the backend uses.
  const params = new URLSearchParams()
  if (q.search?.trim()) params.set('search', q.search.trim())
  ;(q.customerIds ?? []).forEach((c) => params.append('customerIds', c))
  ;(q.siteIds ?? []).forEach((s) => params.append('siteIds', s))
  ;(q.riskLevels ?? []).forEach((r) => params.append('riskLevel', r))
  if (q.sortBy) params.set('sortBy', q.sortBy)
  if (q.sortDir) params.set('sortDir', q.sortDir)
  const pageIndex = q.pageIndex ?? 0
  const pageSize = q.pageSize ?? PAGE_SIZE
  params.set('pageIndex', String(pageIndex))
  params.set('pageSize', String(pageSize))
  const { data } = await api.get(`${API_BASE}/register`, { params })
  return { items: (data.sites ?? []).map(mapListItem), totalCount: data.totalCount ?? 0, pageIndex, pageSize }
}

// Returns the existing asbestosSiteId if the Joblogic site is already in the
// register, or null if it is free to add.
export async function checkSiteExists(siteId: string): Promise<string | null> {
  if (USE_MOCK) return reg.sites.find((s) => s.siteId === siteId)?.asbestosSiteId ?? null
  const { data } = await api.get(`${API_BASE}/register`, { params: { siteIds: siteId, pageSize: 1 } })
  const first = (data.sites ?? [])[0]
  return first ? (first.asbestosSiteId ?? first.id ?? null) : null
}

export async function addSite(customerId: string, siteId: string): Promise<{ asbestosSiteId: string }> {
  if (USE_MOCK) {
    if (reg.sites.some((s) => s.siteId === siteId)) {
      throw new Error('This site already exists in the asbestos register.')
    }
    const now = new Date().toISOString()
    const row: reg.RawSite = { asbestosSiteId: uid('as'), tenantId: 'tenant-linaker', customerId, siteId, createdAt: now, createdById: 'user-sarah', updatedAt: now, updatedById: 'user-sarah' }
    reg.sites.unshift(row)
    reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId: row.asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_CREATED', summary: 'Site created', details: { customer: look.customerName(customerId), siteName: look.siteName(siteId) }, occurredAt: now })
    reg.commit()
    return mockDelay({ asbestosSiteId: row.asbestosSiteId })
  }
  try {
    const { data } = await api.post(`${API_BASE}/register`, { customerId, siteId }, { timeout: 60000 })
    return data
  } catch (e: any) {
    if (e?.response?.status === 409) {
      // Site was already created (e.g. a prior request timed out client-side but
      // succeeded server-side). Return the existing id so the caller can navigate.
      const existingId: string | undefined = e.response.data?.id ?? e.response.data?.asbestosSiteId
      const err: any = new Error('This site is already in the asbestos register.')
      err.asbestosSiteId = existingId
      throw err
    }
    throw e
  }
}

export async function getSiteDetail(asbestosSiteId: string): Promise<SiteDetail> {
  if (USE_MOCK) {
    const s = reg.sites.find((x) => x.asbestosSiteId === asbestosSiteId)
    if (!s) throw new Error('Site not found')
    return mockDelay({
      asbestosSiteId: s.asbestosSiteId,
      customerId: s.customerId,
      customerName: look.customerName(s.customerId),
      siteId: s.siteId,
      siteName: look.siteName(s.siteId),
      createdAt: s.createdAt,
      createdById: s.createdById,
      updatedAt: s.updatedAt,
      updatedById: s.updatedById,
    })
  }
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}`)
  return mapSiteDetail(data.site)
}

// Fetch site header, documents, and ACM entries in parallel via three dedicated endpoints.
export interface SiteFull {
  site: SiteDetail
  documents: SiteDocument[]
  acmEntries: AcmEntry[]
  acmTotalCount: number
}

export async function getSiteFull(asbestosSiteId: string): Promise<SiteFull> {
  if (USE_MOCK) {
    const [site, documents, acmEntries] = await Promise.all([
      getSiteDetail(asbestosSiteId),
      import('./documents.service').then((m) => m.getDocuments(asbestosSiteId)),
      getAcmEntriesPaged(asbestosSiteId, { page: 0, pageSize: PAGE_SIZE }),
    ])
    return { site, documents, acmEntries: acmEntries.items, acmTotalCount: acmEntries.totalCount }
  }
  // Use allSettled so one failing call doesn't blank the whole page.
  const [siteRes, docsRes, acmRes] = await Promise.allSettled([
    api.get(`${API_BASE}/register/${asbestosSiteId}`),
    api.get(`${API_BASE}/register/${asbestosSiteId}/documents`, { params: { page: 0, pageSize: 50 } }),
    api.get(`${API_BASE}/register/${asbestosSiteId}/acm`, { params: { page: 0, pageSize: PAGE_SIZE, statusFilter: 'all' } }),
  ])
  if (siteRes.status === 'rejected') throw siteRes.reason
  if (docsRes.status === 'rejected') throw new Error('Failed to load site documents. Please refresh the page.')
  if (acmRes.status === 'rejected') throw new Error('Failed to load ACM entries. Please refresh the page.')
  return {
    site: mapSiteDetail(siteRes.value.data.site),
    documents: docsRes.status === 'fulfilled' ? (docsRes.value.data.documents ?? []).map(mapDocument) : [],
    acmEntries: acmRes.status === 'fulfilled' ? (acmRes.value.data.acmEntries ?? []).map(mapAcm) : [],
    acmTotalCount: acmRes.status === 'fulfilled' ? (acmRes.value.data.totalCount ?? 0) : 0,
  }
}

// Resolve asset names + run discrepancy detection (single batched check).
function resolveEntry(siteId: string, e: AcmEntry): AcmEntry {
  const exists = look.assetExists(siteId, e.assetId)
  return {
    ...e,
    assetName: e.assetId ? (exists ? look.assetName(siteId, e.assetId) : look.lastKnownAssetName(e.assetId)) : null,
    assetDiscrepancy: !exists,
  }
}

export interface AcmPage {
  items: AcmEntry[]
  totalCount: number
  page: number
  pageSize: number
}

export async function getAcmEntriesPaged(
  asbestosSiteId: string,
  opts: { page?: number; pageSize?: number; statusFilter?: 'active' | 'all' } = {},
): Promise<AcmPage> {
  const page = opts.page ?? 0
  const pageSize = opts.pageSize ?? PAGE_SIZE
  const statusFilter = opts.statusFilter ?? 'all'
  if (USE_MOCK) {
    const s = reg.sites.find((x) => x.asbestosSiteId === asbestosSiteId)!
    const all = reg.acmEntries
      .filter((e) => e.asbestosSiteId === asbestosSiteId)
      .filter((e) => statusFilter === 'all' || e.status === 'ACTIVE')
      .map((e) => resolveEntry(s.siteId, e))
    const start = page * pageSize
    return mockDelay({ items: all.slice(start, start + pageSize), totalCount: all.length, page, pageSize })
  }
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/acm`, {
    params: { page, pageSize, statusFilter },
  })
  // Newest-first by last-updated. NOTE: this sorts the current page only —
  // for correct global ordering across pages the backend should order by
  // updatedAt desc. (Frontend stopgap until backend adds ordering.)
  const items = (data.acmEntries ?? []).map(mapAcm).sort(
    (a: AcmEntry, b: AcmEntry) => (b.updatedAt ?? '').localeCompare(a.updatedAt ?? ''),
  )
  return {
    items,
    totalCount: data.totalCount ?? 0,
    page,
    pageSize,
  }
}

// Keep for backwards compatibility (used by toggleAcmStatus refresh and portal).
export async function getAcmEntries(asbestosSiteId: string): Promise<AcmEntry[]> {
  const result = await getAcmEntriesPaged(asbestosSiteId, { page: 0, pageSize: 200, statusFilter: 'all' })
  return result.items
}

export interface StagedAttachment {
  fileName: string
  file: File // raw File object — passed directly to multipart upload
}

export interface AcmEntryInput {
  buildingTypeId: string
  buildingTypeName: string
  roomLocation: string
  assetId: string | null
  acmTypeId: string
  acmTypeName: string
  condition: AcmEntry['condition']
  riskScore: RiskScore
  notes: string | null
  newAttachments?: StagedAttachment[] // newly staged files to attach on save
  removedAttachmentIds?: string[] // existing attachment ids removed (edit only)
}

// Writes an ACM_DOCUMENT_UPLOADED / ACM_DOCUMENT_REMOVED audit entry per file,
// capturing the linked ACM entry context (Building, Room, ACM Type).
function auditAcmDocument(
  asbestosSiteId: string,
  action: 'ACM_DOCUMENT_UPLOADED' | 'ACM_DOCUMENT_REMOVED',
  e: AcmEntry,
  fileName: string,
  when: string,
) {
  reg.siteAudit.unshift({
    id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones',
    action,
    summary: action === 'ACM_DOCUMENT_UPLOADED' ? 'ACM document uploaded' : 'ACM document removed',
    details: { documentName: fileName, building: e.buildingTypeName, room: e.roomLocation, acmType: e.acmTypeName },
    occurredAt: when,
  })
}

export async function addAcmEntry(asbestosSiteId: string, input: AcmEntryInput): Promise<AcmEntry> {
  if (USE_MOCK) {
    const now = new Date().toISOString()
    const { newAttachments, removedAttachmentIds: _ignored, ...fields } = input
    const entry: AcmEntry = {
      id: uid('acm'), asbestosSiteId, ...fields,
      assetName: null, assetDiscrepancy: false, status: 'ACTIVE',
      attachments: (newAttachments ?? []).map<AcmAttachment>((a) => ({
        id: uid('att'), acmEntryId: '', fileName: a.fileName, uploadedAt: now, uploadedById: 'user-sarah',
      })),
      updatedAt: now, updatedById: 'user-sarah', updatedByName: 'Sarah Jones',
    }
    entry.attachments.forEach((a) => (a.acmEntryId = entry.id))
    reg.acmEntries.push(entry)
    reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'ACM_ENTRY_CREATED', summary: 'ACM entry created', details: { building: input.buildingTypeName, room: input.roomLocation, asset: input.assetId ?? '—', acmType: input.acmTypeName, condition: conditionLabel(input.condition), riskScore: riskLabel(input.riskScore) }, occurredAt: now })
    ;(newAttachments ?? []).forEach((a) => auditAcmDocument(asbestosSiteId, 'ACM_DOCUMENT_UPLOADED', entry, a.fileName, now))
    touchSite(asbestosSiteId, now)
    return mockDelay(entry)
  }
  // Real API: multipart/form-data — text fields + optional files[].
  const { data } = await api.post(`${API_BASE}/register/${asbestosSiteId}/acm`, acmFormData(input), { timeout: 120000 })
  return mapAcm(data.acmEntry ?? data)
}

// Build a multipart FormData body for ACM create/update.
function acmFormData(input: AcmEntryInput, removedAttachmentIds?: string[]): FormData {
  const form = new FormData()
  form.append('buildingTypeId', input.buildingTypeId)
  form.append('roomLocation', input.roomLocation)
  if (input.assetId) form.append('assetId', input.assetId)
  form.append('acmTypeId', input.acmTypeId)
  form.append('condition', input.condition)
  form.append('riskScore', input.riskScore)
  if (input.notes != null) form.append('notes', input.notes)
  for (const att of input.newAttachments ?? []) {
    form.append('files', att.file, att.fileName)
  }
  if (removedAttachmentIds?.length) {
    form.append('removeAttachmentIds', JSON.stringify(removedAttachmentIds))
  }
  return form
}

export async function updateAcmEntry(asbestosSiteId: string, id: string, input: AcmEntryInput): Promise<AcmEntry> {
  if (USE_MOCK) {
    const e = reg.acmEntries.find((x) => x.id === id)!
    const now = new Date().toISOString()
    const { newAttachments, removedAttachmentIds, ...fields } = input
    const site = reg.sites.find((s) => s.asbestosSiteId === asbestosSiteId)

    // Compute a real field-level diff (from → to) before applying changes.
    const changes: Record<string, string> = {}
    if (e.buildingTypeName !== fields.buildingTypeName) changes.building = `${e.buildingTypeName} → ${fields.buildingTypeName}`
    if (e.roomLocation !== fields.roomLocation) changes.roomLocation = `${e.roomLocation} → ${fields.roomLocation}`
    if (e.assetId !== fields.assetId) {
      const fromName = e.assetName ?? '—'
      const toName = fields.assetId && site ? (look.assetName(site.siteId, fields.assetId) ?? look.lastKnownAssetName(fields.assetId)) : '—'
      changes.asset = `${fromName} → ${toName}`
    }
    if (e.acmTypeName !== fields.acmTypeName) changes.acmType = `${e.acmTypeName} → ${fields.acmTypeName}`
    if (e.condition !== fields.condition) changes.condition = `${conditionLabel(e.condition)} → ${conditionLabel(fields.condition)}`
    if (e.riskScore !== fields.riskScore) changes.riskScore = `${riskLabel(e.riskScore)} → ${riskLabel(fields.riskScore)}`
    if ((e.notes ?? '') !== (fields.notes ?? '')) changes.notes = `${e.notes ?? '—'} → ${fields.notes ?? '—'}`

    Object.assign(e, fields, { updatedAt: now, updatedById: 'user-sarah', updatedByName: 'Sarah Jones' })

    if (removedAttachmentIds?.length) {
      for (const rid of removedAttachmentIds) {
        const att = e.attachments.find((a) => a.id === rid)
        if (att) auditAcmDocument(asbestosSiteId, 'ACM_DOCUMENT_REMOVED', e, att.fileName, now)
      }
      e.attachments = e.attachments.filter((a) => !removedAttachmentIds.includes(a.id))
    }
    if (newAttachments?.length) {
      e.attachments.push(
        ...newAttachments.map<AcmAttachment>((a) => ({
          id: uid('att'), acmEntryId: e.id, fileName: a.fileName, uploadedAt: now, uploadedById: 'user-sarah',
        })),
      )
      newAttachments.forEach((a) => auditAcmDocument(asbestosSiteId, 'ACM_DOCUMENT_UPLOADED', e, a.fileName, now))
    }

    if (Object.keys(changes).length) {
      reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: 'ACM_ENTRY_EDITED', summary: 'ACM entry edited', details: { entry: `${e.buildingTypeName}, ${e.roomLocation}`, ...changes }, occurredAt: now })
    }
    touchSite(asbestosSiteId, now)
    return mockDelay({ ...e })
  }
  // Real API: multipart/form-data (PUT) — new files in files[], removals as JSON array string.
  const { data } = await api.put(
    `${API_BASE}/register/${asbestosSiteId}/acm/${id}`,
    acmFormData(input, input.removedAttachmentIds),
    { timeout: 120000 },
  )
  return mapAcm(data.acmEntry ?? data)
}

export async function toggleAcmStatus(asbestosSiteId: string, id: string, status: AcmEntry['status']): Promise<AcmEntry> {
  if (USE_MOCK) {
    const e = reg.acmEntries.find((x) => x.id === id)!
    const from = e.status
    const now = new Date().toISOString()
    e.status = status
    e.updatedAt = now
    reg.siteAudit.unshift({ id: uid('au'), asbestosSiteId, userId: 'user-sarah', userName: 'Sarah Jones', action: status === 'REMEDIATED' ? 'ACM_ENTRY_REMEDIATED' : 'ACM_ENTRY_REACTIVATED', summary: status === 'REMEDIATED' ? 'Entry marked as Remediated' : 'Entry reactivated', details: { building: e.buildingTypeName, room: e.roomLocation, acmType: e.acmTypeName, fromStatus: from, toStatus: status }, occurredAt: now })
    touchSite(asbestosSiteId, now)
    return mockDelay({ ...e })
  }
  const { data } = await api.patch(`${API_BASE}/register/${asbestosSiteId}/acm/${id}/status`, { status })
  return mapAcm(data.acmEntry ?? data)
}

// ─── ACM Attachments ────────────────────────────────────────────────────────

export async function addAcmAttachment(_asbestosSiteId: string, acmEntryId: string, fileName: string): Promise<AcmAttachment> {
  if (USE_MOCK) {
    const now = new Date().toISOString()
    const att: AcmAttachment = { id: uid('att'), acmEntryId, fileName, uploadedAt: now, uploadedById: 'user-sarah' }
    return mockDelay(att)
  }
  // Attachments are sent inline in the create/update multipart body (files[]).
  // This function is not called in the real-API path — addAcmEntry/updateAcmEntry handle it directly.
  return { id: '', acmEntryId, fileName, uploadedAt: new Date(0).toISOString(), uploadedById: '' }
}

export async function removeAcmAttachment(_asbestosSiteId: string, _acmEntryId: string, _attachmentId: string): Promise<void> {
  if (USE_MOCK) return mockDelay(undefined)
  // Removals are sent inline in the update multipart body (removeAttachmentIds JSON array).
  // This function is not called in the real-API path — updateAcmEntry handles it directly.
}

export async function resolveAcmAttachmentUrl(asbestosSiteId: string, acmEntryId: string, attachmentId: string): Promise<string> {
  if (USE_MOCK) return ''
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/acm/${acmEntryId}/attachments/${attachmentId}/download`)
  return data.url
}

function touchSite(asbestosSiteId: string, when: string) {
  const s = reg.sites.find((x) => x.asbestosSiteId === asbestosSiteId)
  if (s) { s.updatedAt = when; s.updatedById = 'user-sarah' }
  reg.commit() // persist mutation so other tabs (QR / portal) see it
}

// MainSubSys-backed lookups for the modals (customers/sites/assets dropdowns).
// `id` is the GUID (used for create); `lookupId` is the numeric MainSubSys id
// (needed to fetch that customer's sites).
export async function getCustomers(search?: string): Promise<LookupOption[]> {
  if (USE_MOCK) {
    const all = [...look.customers].map((c) => ({ ...c, lookupId: c.id })).sort((a, b) => a.name.localeCompare(b.name))
    return mockDelay(search ? all.filter((c) => c.name.toLowerCase().includes(search.toLowerCase())) : all)
  }
  const params: Record<string, string | number> = { pageSize: 50 }
  if (search) params.search = search
  const { data } = await api.get(`${API_BASE}/lookup/customers`, { params })
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  // id = GUID (used everywhere including sites-by-customer lookup now that API uses uniqueId)
  return (data.customers ?? []).map((c: any) => ({ id: c.uniqueId, name: c.name, lookupId: c.uniqueId }))
}

// Customers that already have sites in the register — used by the list filter.
export async function getRegisterCustomers(search = ''): Promise<LookupOption[]> {
  if (USE_MOCK) {
    let opts = reg.sites.map((s) => ({ id: s.customerId, name: look.customerName(s.customerId) }))
    if (search) opts = opts.filter((o) => o.name.toLowerCase().includes(search.toLowerCase()))
    const unique = Array.from(new Map(opts.map((o) => [o.id, o])).values())
    return mockDelay(unique.sort((a, b) => a.name.localeCompare(b.name)))
  }
  try {
    const params: Record<string, string | number> = { pageIndex: 0, pageSize: 50 }
    if (search) params.search = search
    const { data } = await api.get(`${API_BASE}/register/customers`, { params, timeout: 10000 })
    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    return (data.customers ?? [])
      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      .map((c: any) => ({ id: c.customerId, name: c.customerName }))
      .filter((c: LookupOption) => c.id && c.name)
  } catch (e) {
    console.error('[getRegisterCustomers] /register/customers failed:', e)
    return []
  }
}

// Distinct sites currently in the register — used by the Register Site filter.
export async function getRegisteredSites(search = ''): Promise<LookupOption[]> {
  if (USE_MOCK) {
    let opts = reg.sites.map((s) => ({ id: s.siteId, name: look.siteName(s.siteId) }))
    if (search) opts = opts.filter((o) => o.name.toLowerCase().includes(search.toLowerCase()))
    const unique = Array.from(new Map(opts.map((o) => [o.id, o])).values())
    return mockDelay(unique.sort((a, b) => a.name.localeCompare(b.name)))
  }
  try {
    const params: Record<string, string | number> = { pageIndex: 0, pageSize: 50 }
    if (search) params.search = search
    const { data } = await api.get(`${API_BASE}/register/sites`, { params, timeout: 10000 })
    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    return (data.sites ?? [])
      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      .map((s: any) => ({ id: s.siteId, name: s.siteName }))
      .filter((s: LookupOption) => s.id && s.name)
  } catch (e) {
    console.error('[getRegisteredSites] /register/sites failed:', e)
    return []
  }
}

// All sites in the asbestos register keyed by asbestosSiteId — used by Customer Portal site selector.
// /register/sites only has siteId+siteName (no asbestos ID), so we use the main register list.
export async function getPortalSiteList(): Promise<LookupOption[]> {
  if (USE_MOCK) {
    return mockDelay(
      reg.sites.map((s) => ({ id: s.asbestosSiteId, name: look.siteName(s.siteId) }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    )
  }
  const { data } = await api.get(`${API_BASE}/register`, { params: { pageSize: 50 } })
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  return (data.items ?? data.sites ?? []).map((s: any) => ({ id: s.id, name: s.siteName }))
}

// customerUniqueId is the customer GUID — API now uses uniqueId for this lookup.
export async function getSitesByCustomer(customerUniqueId: string): Promise<LookupOption[]> {
  if (USE_MOCK) return mockDelay(look.sites.filter((s) => s.customerId === customerUniqueId).map((s) => ({ ...s, lookupId: s.id })).sort((a, b) => a.name.localeCompare(b.name)))
  if (!customerUniqueId) return []
  const { data } = await api.get(`${API_BASE}/lookup/customers/${customerUniqueId}/sites`, { params: { pageSize: 50 } })
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  return (data.sites ?? []).map((s: any) => ({ id: s.uniqueId ?? s.id, name: s.name }))
}

export async function getAssetsBySite(siteId: string): Promise<LookupOption[]> {
  if (USE_MOCK) {
    const s = reg.sites.find((x) => x.siteId === siteId)
    return mockDelay(s ? (look.assetsBySite[s.siteId] ?? []) : [])
  }
  // Real endpoint: /lookup/sites/{siteId}/assets where siteId is the Joblogic site GUID.
  try {
    const { data } = await api.get(`${API_BASE}/lookup/sites/${siteId}/assets`)
    return (data.assets ?? []).map((a: any) => ({ id: a.uniqueId ?? a.id, name: a.name }))
  } catch {
    return []
  }
}
