import type { SiteDocument, AcmEntry } from '@/types'
import type { AuditActionKey } from '@/utils/auditTaxonomy'
import { loadState, saveState } from '@/utils/persist'

// Stored audit shape in the mock: `action` is the enum KEY (the service derives
// the display label, auditType, and actionKey from it — mirrors the real backend
// which also stores a canonical action and resolves the rest server-side).
export interface RawAuditEntry {
  id: string
  asbestosSiteId: string
  userId: string
  userName: string
  action: AuditActionKey
  summary: string
  details: Record<string, unknown>
  occurredAt: string
}

const TENANT = 'tenant-linaker'

// Registered sites store raw rows (IDs only). The mock service resolves names
// and computes RAG/highest-risk/counts, exactly like the backend will.
export interface RawSite {
  asbestosSiteId: string
  tenantId: string
  customerId: string
  siteId: string
  createdAt: string
  createdById: string
  updatedAt: string
  updatedById: string
}

const SEED_SITES: RawSite[] = [
  { asbestosSiteId: 'as-man', tenantId: TENANT, customerId: 'cust-kfc', siteId: 'site-man-arndale', createdAt: '2026-01-12T08:25:00Z', createdById: 'user-sarah', updatedAt: '2026-05-28T14:22:00Z', updatedById: 'user-sarah' },
  { asbestosSiteId: 'as-leeds', tenantId: TENANT, customerId: 'cust-kfc', siteId: 'site-leeds-crown', createdAt: '2026-02-01T08:25:00Z', createdById: 'user-james', updatedAt: '2026-05-26T10:00:00Z', updatedById: 'user-james' },
  { asbestosSiteId: 'as-birm', tenantId: TENANT, customerId: 'cust-kfc', siteId: 'site-birm-newst', createdAt: '2026-02-10T08:25:00Z', createdById: 'user-sarah', updatedAt: '2026-05-24T09:00:00Z', updatedById: 'user-sarah' },
  { asbestosSiteId: 'as-glas', tenantId: TENANT, customerId: 'cust-kfc', siteId: 'site-glas-buchanan', createdAt: '2026-02-15T08:25:00Z', createdById: 'user-mark', updatedAt: '2026-05-21T09:00:00Z', updatedById: 'user-mark' },
  { asbestosSiteId: 'as-bris', tenantId: TENANT, customerId: 'cust-costa', siteId: 'site-bris-temple', createdAt: '2026-03-01T08:25:00Z', createdById: 'user-mark', updatedAt: '2026-05-19T09:00:00Z', updatedById: 'user-mark' },
  { asbestosSiteId: 'as-edin', tenantId: TENANT, customerId: 'cust-greggs', siteId: 'site-edin-princes', createdAt: '2026-03-10T08:25:00Z', createdById: 'user-james', updatedAt: '2026-05-17T09:00:00Z', updatedById: 'user-james' },
  { asbestosSiteId: 'as-newc', tenantId: TENANT, customerId: 'cust-greggs', siteId: 'site-newc-eldon', createdAt: '2026-03-20T08:25:00Z', createdById: 'user-mark', updatedAt: '2026-05-14T09:00:00Z', updatedById: 'user-mark' },
]

// Documents keyed by asbestosSiteId. KFC Manchester Arndale matches the prototype.
const SEED_DOCUMENTS: SiteDocument[] = [
  { id: 'doc-amp-2026', asbestosSiteId: 'as-man', docType: 'AMP', fileName: 'Asbestos Management Plan 2026.pdf', ampExpiryDate: '2026-09-15', ampExpiryRag: null, isCurrentAmp: true, uploadedAt: '2026-01-12T08:30:00Z', uploadedById: 'user-sarah', uploadedByName: 'Sarah Jones' },
  { id: 'doc-amp-2025', asbestosSiteId: 'as-man', docType: 'AMP', fileName: 'Asbestos Management Plan 2025.pdf', ampExpiryDate: '2026-01-12', ampExpiryRag: null, isCurrentAmp: false, uploadedAt: '2025-01-08T08:30:00Z', uploadedById: 'user-sarah', uploadedByName: 'Sarah Jones' },
  { id: 'doc-survey', asbestosSiteId: 'as-man', docType: 'SURVEY_REPORT', fileName: 'Asbestos Survey Report - Mar 2026.pdf', ampExpiryDate: null, ampExpiryRag: null, isCurrentAmp: false, uploadedAt: '2026-03-15T13:50:00Z', uploadedById: 'user-sarah', uploadedByName: 'Sarah Jones' },
  { id: 'doc-air', asbestosSiteId: 'as-man', docType: 'AIR_MONITORING', fileName: 'Air Monitoring Results.pdf', ampExpiryDate: null, ampExpiryRag: null, isCurrentAmp: false, uploadedAt: '2026-04-02T10:15:00Z', uploadedById: 'user-mark', uploadedByName: 'Mark Davis' },
]

// ACM entries keyed by asbestosSiteId. Note AHU-01 asset (Storage Annex / Plant
// room) is intentionally NOT in lookups.assetsBySite → triggers discrepancy demo.
const SEED_ACM_ENTRIES: AcmEntry[] = [
  {
    id: 'acm-1', asbestosSiteId: 'as-man', buildingTypeId: 'bt-main', buildingTypeName: 'Main Building',
    roomLocation: 'Basement pipework', assetId: 'asset-boiler-3', assetName: null, assetDiscrepancy: false,
    acmTypeId: 'at-pipe', acmTypeName: 'Pipe Lagging', condition: 'HIGH_DAMAGE', riskScore: 'HIGH',
    notes: 'Do not disturb. Significant deterioration noted — schedule removal.', status: 'ACTIVE',
    attachments: [
      { id: 'att-1', acmEntryId: 'acm-1', fileName: 'basement-pipe-01.jpg', uploadedAt: '2026-05-28T14:00:00Z', uploadedById: 'user-sarah' },
      { id: 'att-2', acmEntryId: 'acm-1', fileName: 'basement-pipe-02.jpg', uploadedAt: '2026-05-28T14:01:00Z', uploadedById: 'user-sarah' },
    ],
    updatedAt: '2026-05-28T14:22:00Z', updatedById: 'user-sarah', updatedByName: 'Sarah Jones',
  },
  {
    id: 'acm-2', asbestosSiteId: 'as-man', buildingTypeId: 'bt-main', buildingTypeName: 'Main Building',
    roomLocation: 'Kitchen ceiling', assetId: null, assetName: null, assetDiscrepancy: false,
    acmTypeId: 'at-textured', acmTypeName: 'Textured Coating', condition: 'LOW_DAMAGE', riskScore: 'MEDIUM',
    notes: null, status: 'ACTIVE', attachments: [],
    updatedAt: '2026-05-28T14:18:00Z', updatedById: 'user-sarah', updatedByName: 'Sarah Jones',
  },
  {
    id: 'acm-3', asbestosSiteId: 'as-man', buildingTypeId: 'bt-main', buildingTypeName: 'Main Building',
    roomLocation: 'Staff room', assetId: null, assetName: null, assetDiscrepancy: false,
    acmTypeId: 'at-floor', acmTypeName: 'Floor Tiles', condition: 'GOOD', riskScore: 'LOW',
    notes: null, status: 'ACTIVE', attachments: [],
    updatedAt: '2026-05-25T09:40:00Z', updatedById: 'user-sarah', updatedByName: 'Sarah Jones',
  },
  {
    id: 'acm-4', asbestosSiteId: 'as-man', buildingTypeId: 'bt-storage', buildingTypeName: 'Storage Annex',
    roomLocation: 'Plant room', assetId: 'asset-ahu-01', assetName: null, assetDiscrepancy: false,
    acmTypeId: 'at-insboard', acmTypeName: 'Insulation Board', condition: 'MEDIUM_DAMAGE', riskScore: 'HIGH',
    notes: 'Encapsulated. Labelled.', status: 'ACTIVE',
    attachments: [
      { id: 'att-3', acmEntryId: 'acm-4', fileName: 'plant-room-board.jpg', uploadedAt: '2026-05-22T16:00:00Z', uploadedById: 'user-mark' },
    ],
    updatedAt: '2026-05-22T16:05:00Z', updatedById: 'user-mark', updatedByName: 'Mark Davis',
  },
  {
    id: 'acm-5', asbestosSiteId: 'as-man', buildingTypeId: 'bt-storage', buildingTypeName: 'Storage Annex',
    roomLocation: 'Roof space', assetId: null, assetName: null, assetDiscrepancy: false,
    acmTypeId: 'at-sprayed', acmTypeName: 'Sprayed Coating', condition: 'GOOD', riskScore: 'MEDIUM',
    notes: null, status: 'REMEDIATED', attachments: [],
    updatedAt: '2026-05-20T11:30:00Z', updatedById: 'user-mark', updatedByName: 'Mark Davis',
  },
]

const SEED_SITE_AUDIT: RawAuditEntry[] = [
  { id: 'au-1', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'ACM_ENTRY_EDITED', summary: 'Risk score updated', details: { entry: 'Main Building, Basement pipework, Pipe Lagging', fieldChanged: 'Risk Score', previousValue: 'Medium', newValue: 'High' }, occurredAt: '2026-05-28T14:22:00Z' },
  { id: 'au-2', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'ACM_ENTRY_CREATED', summary: 'ACM entry created', details: { building: 'Main Building', room: 'Kitchen ceiling', asset: '—', acmType: 'Textured Coating', condition: 'Low Damage', riskScore: 'Medium' }, occurredAt: '2026-05-28T14:18:00Z' },
  { id: 'au-3', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'ACM_ENTRY_CREATED', summary: 'ACM entry created', details: { building: 'Main Building', room: 'Staff room', asset: '—', acmType: 'Floor Tiles', condition: 'Good', riskScore: 'Low' }, occurredAt: '2026-05-25T09:40:00Z' },
  { id: 'au-4', asbestosSiteId: 'as-man', userId: 'user-mark', userName: 'Mark Davis', action: 'ACM_ENTRY_CREATED', summary: 'ACM entry created', details: { building: 'Storage Annex', room: 'Plant room', asset: 'AHU-01', acmType: 'Insulation Board', condition: 'Medium Damage', riskScore: 'High' }, occurredAt: '2026-05-22T16:05:00Z' },
  { id: 'au-5', asbestosSiteId: 'as-man', userId: 'user-mark', userName: 'Mark Davis', action: 'ACM_ENTRY_REMEDIATED', summary: 'Entry marked as Remediated', details: { building: 'Storage Annex', room: 'Roof space', acmType: 'Sprayed Coating' }, occurredAt: '2026-05-20T11:30:00Z' },
  { id: 'au-6', asbestosSiteId: 'as-man', userId: 'user-mark', userName: 'Mark Davis', action: 'ACM_ENTRY_EDITED', summary: 'Condition updated', details: { entry: 'Storage Annex, Roof space', fieldChanged: 'Condition', previousValue: 'Medium Damage', newValue: 'Good' }, occurredAt: '2026-05-20T11:28:00Z' },
  { id: 'au-7', asbestosSiteId: 'as-man', userId: 'user-mark', userName: 'Mark Davis', action: 'SITE_DOCUMENT_UPLOADED', summary: 'Site document uploaded', details: { documentName: 'Air Monitoring Results.pdf', documentType: 'Air Monitoring', fileSize: '512 KB' }, occurredAt: '2026-04-02T10:15:00Z' },
  { id: 'au-8', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_DOCUMENT_UPLOADED', summary: 'Site document uploaded', details: { documentName: 'Asbestos Survey Report - Mar 2026.pdf', documentType: 'Survey Report', fileSize: '1.2 MB' }, occurredAt: '2026-03-15T13:50:00Z' },
  { id: 'au-9', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_DOCUMENT_UPLOADED', summary: 'Site document uploaded', details: { documentName: 'Asbestos Management Plan 2026.pdf', documentType: 'AMP', fileSize: '2.4 MB' }, occurredAt: '2026-01-12T08:30:00Z' },
  { id: 'au-10', asbestosSiteId: 'as-man', userId: 'user-sarah', userName: 'Sarah Jones', action: 'SITE_CREATED', summary: 'Site created', details: { customer: 'KFC', siteName: 'KFC - Manchester Arndale' }, occurredAt: '2026-01-12T08:25:00Z' },
]

// ─── Shared persistent mock state ────────────────────────────────────────────
// Hydrate from localStorage (seed on first run). All tabs read/write the same
// keys, so changes in the admin tab are visible in the QR / portal preview tab.
const KEY = 'asb_register_v1'

export const sites: RawSite[] = loadState(`${KEY}_sites`, SEED_SITES)
export const documents: SiteDocument[] = loadState(`${KEY}_documents`, SEED_DOCUMENTS)
export const acmEntries: AcmEntry[] = loadState(`${KEY}_acm`, SEED_ACM_ENTRIES)
export const siteAudit: RawAuditEntry[] = loadState(`${KEY}_audit`, SEED_SITE_AUDIT)

// Persist current state. Services call this after every mutation.
export function commit(): void {
  saveState(`${KEY}_sites`, sites)
  saveState(`${KEY}_documents`, documents)
  saveState(`${KEY}_acm`, acmEntries)
  saveState(`${KEY}_audit`, siteAudit)
}

// Reset to seed data (handy for testing). Exposed on window for convenience.
export function resetMockState(): void {
  ;[`${KEY}_sites`, `${KEY}_documents`, `${KEY}_acm`, `${KEY}_audit`].forEach((k) => localStorage.removeItem(k))
  location.reload()
}
if (typeof window !== 'undefined') (window as unknown as { resetAsbestosMock: () => void }).resetAsbestosMock = resetMockState
