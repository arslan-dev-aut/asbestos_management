// Audit taxonomy for the site-level register audit trail.
// Audit Type → Actions, per the Technical Scope. The "Action" stored on each
// audit entry is one of these keys; auditType is derived from it.

export type AuditType =
  | 'SITE_MANAGEMENT'
  | 'ACM_MANAGEMENT'
  | 'DOCUMENT_MANAGEMENT'
  | 'CONFIGURATION'

export type AuditActionKey =
  // Asbestos Site Management
  | 'SITE_CREATED'
  // Asbestos ACM Management
  | 'ACM_ENTRY_CREATED'
  | 'ACM_ENTRY_EDITED'
  | 'ACM_ENTRY_REMEDIATED'
  | 'ACM_ENTRY_REACTIVATED'
  // Asbestos Document Management
  | 'SITE_DOCUMENT_UPLOADED'
  | 'SITE_DOCUMENT_REMOVED'
  | 'AMP_REPLACED'
  | 'AMP_EXPIRY_UPDATED'
  | 'ACM_DOCUMENT_UPLOADED'
  | 'ACM_DOCUMENT_REMOVED'
  // Asbestos Configuration
  | 'BUILDING_TYPE_ADDED'
  | 'BUILDING_TYPE_DEACTIVATED'
  | 'BUILDING_TYPE_REACTIVATED'
  | 'ACM_TYPE_ADDED'
  | 'ACM_TYPE_DEACTIVATED'
  | 'ACM_TYPE_REACTIVATED'

export const auditTypeLabels: Record<AuditType, string> = {
  SITE_MANAGEMENT: 'Asbestos Site Management',
  ACM_MANAGEMENT: 'Asbestos ACM Management',
  DOCUMENT_MANAGEMENT: 'Asbestos Document Management',
  CONFIGURATION: 'Asbestos Configuration',
}

export const actionLabels: Record<AuditActionKey, string> = {
  SITE_CREATED: 'Site Created',
  ACM_ENTRY_CREATED: 'ACM Entry Created',
  ACM_ENTRY_EDITED: 'ACM Entry Edited',
  ACM_ENTRY_REMEDIATED: 'ACM Entry Marked Remediated',
  ACM_ENTRY_REACTIVATED: 'ACM Entry Reactivated',
  SITE_DOCUMENT_UPLOADED: 'Site Document Uploaded',
  SITE_DOCUMENT_REMOVED: 'Site Document Removed',
  AMP_REPLACED: 'AMP Replaced',
  AMP_EXPIRY_UPDATED: 'AMP Expiry Date Updated',
  ACM_DOCUMENT_UPLOADED: 'ACM Document Uploaded',
  ACM_DOCUMENT_REMOVED: 'ACM Document Removed',
  BUILDING_TYPE_ADDED: 'Building Type Added',
  BUILDING_TYPE_DEACTIVATED: 'Building Type Deactivated',
  BUILDING_TYPE_REACTIVATED: 'Building Type Reactivated',
  ACM_TYPE_ADDED: 'ACM Type Added',
  ACM_TYPE_DEACTIVATED: 'ACM Type Deactivated',
  ACM_TYPE_REACTIVATED: 'ACM Type Reactivated',
}

// Which actions belong to which audit type (drives the dependent dropdown).
export const actionsByType: Record<AuditType, AuditActionKey[]> = {
  SITE_MANAGEMENT: ['SITE_CREATED'],
  ACM_MANAGEMENT: ['ACM_ENTRY_CREATED', 'ACM_ENTRY_EDITED', 'ACM_ENTRY_REMEDIATED', 'ACM_ENTRY_REACTIVATED'],
  DOCUMENT_MANAGEMENT: ['SITE_DOCUMENT_UPLOADED', 'SITE_DOCUMENT_REMOVED', 'AMP_REPLACED', 'AMP_EXPIRY_UPDATED', 'ACM_DOCUMENT_UPLOADED', 'ACM_DOCUMENT_REMOVED'],
  CONFIGURATION: ['BUILDING_TYPE_ADDED', 'BUILDING_TYPE_DEACTIVATED', 'BUILDING_TYPE_REACTIVATED', 'ACM_TYPE_ADDED', 'ACM_TYPE_DEACTIVATED', 'ACM_TYPE_REACTIVATED'],
}

export function auditTypeOf(action: AuditActionKey): AuditType {
  return (Object.keys(actionsByType) as AuditType[]).find((t) => actionsByType[t].includes(action)) ?? 'SITE_MANAGEMENT'
}

// Backend sends auditType as ASBESTOS_* enums; map to/from the frontend AuditType.
export const backendToFrontendAuditType: Record<string, AuditType> = {
  ASBESTOS_SITE: 'SITE_MANAGEMENT',
  ASBESTOS_ACM: 'ACM_MANAGEMENT',
  ASBESTOS_DOCUMENT: 'DOCUMENT_MANAGEMENT',
  ASBESTOS_CONFIGURATION: 'CONFIGURATION',
}
export const frontendToBackendAuditType: Record<AuditType, string> = {
  SITE_MANAGEMENT: 'ASBESTOS_SITE',
  ACM_MANAGEMENT: 'ASBESTOS_ACM',
  DOCUMENT_MANAGEMENT: 'ASBESTOS_DOCUMENT',
  CONFIGURATION: 'ASBESTOS_CONFIGURATION',
}

// Coloured dot per audit type for the trail.
export const auditTypeDot: Record<AuditType, string> = {
  SITE_MANAGEMENT: 'bg-jl-teal',
  ACM_MANAGEMENT: 'bg-rag-green',
  DOCUMENT_MANAGEMENT: 'bg-rag-amber',
  CONFIGURATION: 'bg-jl-navy',
}
