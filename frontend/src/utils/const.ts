import type { Condition, RiskScore, DocType, RagColour } from '@/types'

export const PAGE_SIZE = 10 // default for Register list and ACM entries

export const ACCEPTED_FILE_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
export const ACCEPTED_FILE_EXT = '.pdf,.jpg,.jpeg,.png'
export const ACCEPTED_BULK_EXT = '.csv,.xlsx'

export const AMP_EXPIRY_WARN_DAYS = 30 // fixed threshold for this delivery

export const conditions: { value: Condition; label: string }[] = [
  { value: 'GOOD', label: 'Good' },
  { value: 'LOW_DAMAGE', label: 'Low Damage' },
  { value: 'MEDIUM_DAMAGE', label: 'Medium Damage' },
  { value: 'HIGH_DAMAGE', label: 'High Damage' },
]

export const riskScores: { value: RiskScore; label: string; rag: RagColour }[] = [
  { value: 'LOW', label: 'Low', rag: 'GREEN' },
  { value: 'MEDIUM', label: 'Medium', rag: 'AMBER' },
  { value: 'HIGH', label: 'High', rag: 'RED' },
]

export const documentTypes: { value: DocType; label: string }[] = [
  { value: 'AMP', label: 'AMP' },
  { value: 'SURVEY_REPORT', label: 'Survey Report' },
  { value: 'AIR_MONITORING', label: 'Air Monitoring' },
  { value: 'OTHER', label: 'Other' },
]

export const acmStatuses = [
  { value: 'ACTIVE', label: 'Active', rag: 'GREEN' as RagColour },
  { value: 'REMEDIATED', label: 'Remediated', rag: 'NONE' as RagColour },
]

// Label maps for display
export const conditionLabel = (c: Condition) =>
  conditions.find((x) => x.value === c)?.label ?? c
export const riskLabel = (r: RiskScore) =>
  riskScores.find((x) => x.value === r)?.label ?? r
export const docTypeLabel = (d: DocType) =>
  documentTypes.find((x) => x.value === d)?.label ?? d
