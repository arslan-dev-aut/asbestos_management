// Shared domain types — mirror the Technical Scope Document data models.
// Every persisted entity carries tenantId (mandatory client requirement);
// names (customer/site/asset/user) are resolved from MainSubSys at read time
// and are NOT stored in our DB — they appear here only on read responses.

export type RagColour = 'GREEN' | 'AMBER' | 'RED' | 'NONE'
export type RiskScore = 'LOW' | 'MEDIUM' | 'HIGH'
export type Condition = 'GOOD' | 'LOW_DAMAGE' | 'MEDIUM_DAMAGE' | 'HIGH_DAMAGE'
export type AcmStatus = 'ACTIVE' | 'REMEDIATED'
export type DocType = 'AMP' | 'SURVEY_REPORT' | 'AIR_MONITORING' | 'OTHER'

// ─── Configuration ────────────────────────────────────────────────────────
export interface BuildingType {
  id: string
  name: string
  isActive: boolean
  createdAt: string
  createdBy: string
}

export interface AcmType {
  id: string
  name: string
  isActive: boolean
  createdAt: string
  createdBy: string
}

// Configuration audit (third sub-tab) — add / activate / deactivate history
export type ConfigAuditAction = 'TYPE_ADDED' | 'TYPE_ACTIVATED' | 'TYPE_DEACTIVATED'
export interface ConfigAuditEntry {
  id: string
  category: 'BUILDING_TYPE' | 'ACM_TYPE'
  typeName: string
  action: ConfigAuditAction
  userId: string
  userName: string
  occurredAt: string
}

// ─── Register ─────────────────────────────────────────────────────────────
export interface SiteListItem {
  asbestosSiteId: string
  customerId: string
  customerName: string // resolved from MainSubSys
  siteId: string
  siteName: string // resolved from MainSubSys
  totalAcm: number
  activeAcm: number
  highestRisk: RiskScore | 'NONE'
  ampExpiryDate: string | null
  ampExpiryRag: RagColour
  lastUpdated: string
  updatedById: string
  updatedByName: string // resolved from MainSubSys
}

export interface SiteDetail {
  asbestosSiteId: string
  customerId: string
  customerName: string
  siteId: string
  siteName: string
  createdAt: string
  createdById: string
  updatedAt: string
  updatedById: string
}

export interface SiteDocument {
  id: string
  asbestosSiteId: string
  docType: DocType
  fileName: string
  fileKey?: string | null // mock only
  fileUrl?: string | null
  downloadUrl?: string | null // real backend: presigned URL from list response
  ampExpiryDate: string | null // only for AMP docs
  ampExpiryRag: RagColour | null // computed, AMP only
  isCurrentAmp: boolean // false = superseded
  uploadedAt: string
  uploadedById: string
  uploadedByName: string
}

export interface AcmAttachment {
  id: string
  acmEntryId?: string
  fileName: string
  fileKey?: string | null // mock only
  fileUrl?: string | null
  downloadUrl?: string | null // real backend: presigned URL from list response
  uploadedAt?: string
  uploadedById?: string
}

export interface AcmEntry {
  id: string
  asbestosSiteId: string
  buildingTypeId: string
  buildingTypeName: string
  roomLocation: string
  assetId: string | null
  assetName: string | null // null if discrepancy
  assetDiscrepancy: boolean
  acmTypeId: string
  acmTypeName: string
  condition: Condition
  riskScore: RiskScore
  notes: string | null
  status: AcmStatus
  attachments: AcmAttachment[]
  updatedAt?: string
  updatedById?: string
  updatedByName?: string
}

// ─── Audit (site level) ─────────────────────────────────────────────────────
// Action keys + audit-type taxonomy live in utils/auditTaxonomy.ts
import type { AuditActionKey, AuditType } from '@/utils/auditTaxonomy'

export interface AuditLogEntry {
  id: string
  asbestosSiteId: string
  userId: string
  userName: string
  auditType: AuditType // resolved from backend ASBESTOS_* enum
  action: string // human-readable action label as sent by the backend
  actionKey: AuditActionKey // normalised key for icon/colour lookup
  summary: string // human-readable one-liner for the collapsed row
  details: Record<string, unknown> // expanded "Detail Captured" payload (dropdown content)
  occurredAt: string
}

// ─── Bulk ─────────────────────────────────────────────────────────────────
export interface BulkUploadRow {
  rowIndex: number
  status: 'VALID' | 'ERROR'
  errorDetail: string | null
  customerName: string
  siteName: string
  building: string
  roomLocation: string
  asset: string | null
  acmType: string
  condition: string
  riskScore: string
  notes: string | null
}

export interface BulkValidationResult {
  success?: boolean
  message?: string | null
  rows: BulkUploadRow[]
  validCount: number
  errorCount: number
  sitesToCreate: string[]
  uploadToken: string
}

// ─── QR ─────────────────────────────────────────────────────────────────────
export interface QrCode {
  token: string
  qrImageUrl: string
  previewUrl: string
  generatedAt: string
  generatedBy: string
}

// Read-only site payload shared by the QR public page and the View-Only
// portal tabs. `acmEntries` are full entries so the shared table can render
// Notes, Status and attachments consistently across all read-only views.
export interface ReadonlySiteData {
  siteName: string
  customerName: string
  acmEntries: AcmEntry[]
  documents: SiteDocument[] // current AMP only + survey/air; no superseded
}

// ─── MainSubSys lookups (resolved by ID) ────────────────────────────────────
export interface LookupOption {
  id: string // GUID (uniqueId) — used for create / register filtering
  name: string
  lookupId?: string // numeric MainSubSys id — used to fetch sub-resources (e.g. sites by customer)
}

// ─── Generic API envelope ────────────────────────────────────────────────────
export interface ApiResponse<T> {
  success: boolean
  message?: string
  data: T
}

export interface Paginated<T> {
  items: T[]
  totalCount: number
  pageIndex: number
  pageSize: number
}
