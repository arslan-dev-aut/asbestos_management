import { api, API_BASE, USE_MOCK, mockDelay, uid } from './api'
import * as mock from '@/mocks/configuration'
import type { BuildingType, AcmType, ConfigAuditEntry } from '@/types'

// ─── Building Types ──────────────────────────────────────────────────────────
export async function getBuildingTypes(activeOnly = false): Promise<BuildingType[]> {
  if (USE_MOCK) {
    const data = mock.buildingTypes.filter((t) => (activeOnly ? t.isActive : true))
    return mockDelay([...data])
  }
  // Real API: omit activeOnly to get ALL; activeOnly=true → active only,
  // activeOnly=false → inactive only. Our `activeOnly=false` default means "all".
  const params: Record<string, unknown> = { pageSize: 50 }
  if (activeOnly) params.activeOnly = true
  const { data } = await api.get(`${API_BASE}/config/building-types`, { params })
  return (data.buildingTypes ?? data.items ?? data ?? []).map((t: any) => ({
    id: t.id,
    name: t.name,
    isActive: t.isActive ?? t.active ?? true,
    createdAt: t.createdAt ?? '',
    createdBy: t.createdBy ?? '',
  }))
}

export async function addBuildingType(name: string): Promise<BuildingType> {
  if (USE_MOCK) {
    const bt: BuildingType = { id: uid('bt'), name, isActive: true, createdAt: new Date().toISOString(), createdBy: 'user-sarah' }
    mock.buildingTypes.push(bt)
    mock.configAudit.unshift({ id: uid('ca'), category: 'BUILDING_TYPE', typeName: name, action: 'TYPE_ADDED', userId: 'user-sarah', userName: 'Sarah Jones', occurredAt: bt.createdAt })
    mock.commit()
    return mockDelay(bt)
  }
  const { data } = await api.post(`${API_BASE}/config/building-types`, { name })
  return data.buildingType
}

export async function toggleBuildingType(id: string, isActive: boolean): Promise<BuildingType> {
  if (USE_MOCK) {
    const bt = mock.buildingTypes.find((t) => t.id === id)!
    bt.isActive = isActive
    mock.configAudit.unshift({ id: uid('ca'), category: 'BUILDING_TYPE', typeName: bt.name, action: isActive ? 'TYPE_ACTIVATED' : 'TYPE_DEACTIVATED', userId: 'user-sarah', userName: 'Sarah Jones', occurredAt: new Date().toISOString() })
    mock.commit()
    return mockDelay({ ...bt })
  }
  const { data } = await api.patch(`${API_BASE}/config/building-types/${id}`, { isActive })
  return data.buildingType
}

// ─── ACM Types ────────────────────────────────────────────────────────────────
export async function getAcmTypes(activeOnly = false): Promise<AcmType[]> {
  if (USE_MOCK) {
    const data = mock.acmTypes.filter((t) => (activeOnly ? t.isActive : true))
    return mockDelay([...data])
  }
  const params: Record<string, unknown> = { pageSize: 50 }
  if (activeOnly) params.activeOnly = true
  const { data } = await api.get(`${API_BASE}/config/acm-types`, { params })
  return (data.acmTypes ?? data.items ?? data ?? []).map((t: any) => ({
    id: t.id,
    name: t.name,
    isActive: t.isActive ?? t.active ?? true,
    createdAt: t.createdAt ?? '',
    createdBy: t.createdBy ?? '',
  }))
}

export async function addAcmType(name: string): Promise<AcmType> {
  if (USE_MOCK) {
    const at: AcmType = { id: uid('at'), name, isActive: true, createdAt: new Date().toISOString(), createdBy: 'user-sarah' }
    mock.acmTypes.push(at)
    mock.configAudit.unshift({ id: uid('ca'), category: 'ACM_TYPE', typeName: name, action: 'TYPE_ADDED', userId: 'user-sarah', userName: 'Sarah Jones', occurredAt: at.createdAt })
    mock.commit()
    return mockDelay(at)
  }
  const { data } = await api.post(`${API_BASE}/config/acm-types`, { name })
  return data.acmType
}

export async function toggleAcmType(id: string, isActive: boolean): Promise<AcmType> {
  if (USE_MOCK) {
    const at = mock.acmTypes.find((t) => t.id === id)!
    at.isActive = isActive
    mock.configAudit.unshift({ id: uid('ca'), category: 'ACM_TYPE', typeName: at.name, action: isActive ? 'TYPE_ACTIVATED' : 'TYPE_DEACTIVATED', userId: 'user-sarah', userName: 'Sarah Jones', occurredAt: new Date().toISOString() })
    mock.commit()
    return mockDelay({ ...at })
  }
  const { data } = await api.patch(`${API_BASE}/config/acm-types/${id}`, { isActive })
  return data.acmType
}

// ─── Configuration Audit (third sub-tab) ────────────────────────────────────
// Real API returns human-readable action strings ("Building Type Added") under
// auditType ASBESTOS_CONFIGURATION, with details { name, typeId, isActive? }.
// Map them to the panel's ConfigAuditEntry shape (category / typeName / action).
interface RawAuditEntry {
  id: string
  userName: string | null
  action: string
  details?: { name?: string; typeId?: string; isActive?: boolean }
  occurredAt: string
}

function mapConfigAudit(e: RawAuditEntry): ConfigAuditEntry {
  const category = /acm type/i.test(e.action) ? 'ACM_TYPE' : 'BUILDING_TYPE'
  const action: ConfigAuditEntry['action'] = /added/i.test(e.action)
    ? 'TYPE_ADDED'
    : /deactivated/i.test(e.action)
      ? 'TYPE_DEACTIVATED'
      : 'TYPE_ACTIVATED'
  return {
    id: e.id,
    category,
    typeName: e.details?.name ?? '—',
    action,
    userId: '',
    userName: e.userName ?? '—',
    occurredAt: e.occurredAt,
  }
}

export async function getConfigAudit(): Promise<ConfigAuditEntry[]> {
  if (USE_MOCK) return mockDelay([...mock.configAudit])
  const { data } = await api.get(`${API_BASE}/audit/config`, { params: { pageSize: 50 } })
  /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
  const raw: RawAuditEntry[] = data.entries ?? data.items ?? data ?? []
  return raw.map(mapConfigAudit)
}
