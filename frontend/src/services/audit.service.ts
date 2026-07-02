import { api, API_BASE, USE_MOCK, mockDelay } from './api'
import * as reg from '@/mocks/register'
import { PAGE_SIZE } from '@/utils/const'
import { actionLabels, backendToFrontendAuditType, frontendToBackendAuditType, auditTypeOf } from '@/utils/auditTaxonomy'
import type { AuditActionKey, AuditType } from '@/utils/auditTaxonomy'
import type { AuditLogEntry, Paginated } from '@/types'

// Backend sends `action` as a human-readable label ("ACM Entry Created"). Map it
// back to the enum key used for icon/colour lookup. Falls back to the raw string.
const labelToKey = Object.fromEntries(
  (Object.entries(actionLabels) as [AuditActionKey, string][]).map(([k, v]) => [v.toLowerCase(), k]),
) as Record<string, AuditActionKey>

function actionKeyOf(raw: string): AuditActionKey {
  if (raw in actionLabels) return raw as AuditActionKey
  return labelToKey[raw.toLowerCase()] ?? (raw as AuditActionKey)
}

export interface AuditQuery {
  pageIndex?: number
  pageSize?: number
  auditTypes?: AuditType[] // frontend enums; mapped to backend ASBESTOS_* here
  actions?: string[] // human-readable action labels (backend filter values)
}

export async function getSiteAudit(
  asbestosSiteId: string,
  query: AuditQuery = {},
): Promise<Paginated<AuditLogEntry>> {
  const pageIndex = query.pageIndex ?? 0
  const pageSize = query.pageSize ?? PAGE_SIZE
  const auditTypes = query.auditTypes ?? []
  const actions = query.actions ?? []

  if (USE_MOCK) {
    let all = reg.siteAudit
      .filter((a) => a.asbestosSiteId === asbestosSiteId)
      .sort((a, b) => (b.occurredAt > a.occurredAt ? 1 : -1))
    if (auditTypes.length) all = all.filter((e) => auditTypes.includes(auditTypeOf(e.action)))
    if (actions.length) all = all.filter((e) => actions.includes(actionLabels[e.action]) || actions.includes(e.action))
    const items: AuditLogEntry[] = all.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize).map((e) => ({
      ...e,
      auditType: auditTypeOf(e.action),
      action: actionLabels[e.action] ?? e.action,
      actionKey: e.action,
    }))
    return mockDelay({ items, totalCount: all.length, pageIndex, pageSize })
  }

  // Real API supports server-side filtering + pagination. Multi-select filters
  // are sent as repeated query params (FastAPI-style).
  const params = new URLSearchParams()
  params.set('pageIndex', String(pageIndex))
  params.set('pageSize', String(pageSize))
  auditTypes.forEach((t) => params.append('auditType', frontendToBackendAuditType[t])) // backend ASBESTOS_* enum
  actions.forEach((a) => params.append('action', a)) // backend expects the human-readable label
  const { data } = await api.get(`${API_BASE}/register/${asbestosSiteId}/audit`, { params })

  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  const items: AuditLogEntry[] = (data.entries ?? []).map((e: any) => ({
    id: e.id,
    asbestosSiteId: e.asbestosSiteId ?? asbestosSiteId,
    userId: e.userId ?? '',
    userName: e.userName ?? '—',
    auditType: backendToFrontendAuditType[e.auditType] ?? auditTypeOf(actionKeyOf(e.action ?? '')),
    action: e.action ?? '',
    actionKey: actionKeyOf(e.action ?? ''),
    summary: e.action ?? '',
    details: e.details ?? {},
    occurredAt: e.occurredAt,
  }))
  return { items, totalCount: data.totalCount ?? items.length, pageIndex, pageSize }
}
