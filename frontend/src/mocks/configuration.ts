import type { BuildingType, AcmType, ConfigAuditEntry } from '@/types'
import { loadState, saveState } from '@/utils/persist'

const SEED_BUILDING_TYPES: BuildingType[] = [
  { id: 'bt-main', name: 'Main Building', isActive: true, createdAt: '2026-01-05T09:00:00Z', createdBy: 'user-sarah' },
  { id: 'bt-kitchen', name: 'Kitchen Block', isActive: true, createdAt: '2026-01-05T09:01:00Z', createdBy: 'user-sarah' },
  { id: 'bt-storage', name: 'Storage Annex', isActive: true, createdAt: '2026-01-05T09:02:00Z', createdBy: 'user-sarah' },
  { id: 'bt-plant', name: 'Plant Room', isActive: true, createdAt: '2026-01-05T09:03:00Z', createdBy: 'user-mark' },
  { id: 'bt-outbuilding', name: 'Outbuilding', isActive: false, createdAt: '2026-01-05T09:04:00Z', createdBy: 'user-mark' },
]

const SEED_ACM_TYPES: AcmType[] = [
  { id: 'at-pipe', name: 'Pipe Lagging', isActive: true, createdAt: '2026-01-05T09:10:00Z', createdBy: 'user-sarah' },
  { id: 'at-insboard', name: 'Insulation Board', isActive: true, createdAt: '2026-01-05T09:11:00Z', createdBy: 'user-sarah' },
  { id: 'at-sprayed', name: 'Sprayed Coating', isActive: true, createdAt: '2026-01-05T09:12:00Z', createdBy: 'user-sarah' },
  { id: 'at-floor', name: 'Floor Tiles', isActive: true, createdAt: '2026-01-05T09:13:00Z', createdBy: 'user-mark' },
  { id: 'at-textured', name: 'Textured Coating', isActive: true, createdAt: '2026-01-05T09:14:00Z', createdBy: 'user-mark' },
  { id: 'at-cement', name: 'Cement Sheet', isActive: true, createdAt: '2026-01-05T09:15:00Z', createdBy: 'user-mark' },
  { id: 'at-gaskets', name: 'Gaskets/Rope', isActive: false, createdAt: '2026-01-05T09:16:00Z', createdBy: 'user-mark' },
  { id: 'at-other', name: 'Other', isActive: true, createdAt: '2026-01-05T09:17:00Z', createdBy: 'user-sarah' },
]

const SEED_CONFIG_AUDIT: ConfigAuditEntry[] = [
  { id: 'ca-1', category: 'BUILDING_TYPE', typeName: 'Outbuilding', action: 'TYPE_DEACTIVATED', userId: 'user-mark', userName: 'Mark Davis', occurredAt: '2026-05-10T11:00:00Z' },
  { id: 'ca-2', category: 'ACM_TYPE', typeName: 'Gaskets/Rope', action: 'TYPE_DEACTIVATED', userId: 'user-mark', userName: 'Mark Davis', occurredAt: '2026-05-09T15:30:00Z' },
  { id: 'ca-3', category: 'ACM_TYPE', typeName: 'Cement Sheet', action: 'TYPE_ADDED', userId: 'user-mark', userName: 'Mark Davis', occurredAt: '2026-01-05T09:15:00Z' },
  { id: 'ca-4', category: 'BUILDING_TYPE', typeName: 'Plant Room', action: 'TYPE_ADDED', userId: 'user-mark', userName: 'Mark Davis', occurredAt: '2026-01-05T09:03:00Z' },
]

// ─── Shared persistent mock state ────────────────────────────────────────────
const KEY = 'asb_config_v1'
export const buildingTypes: BuildingType[] = loadState(`${KEY}_building`, SEED_BUILDING_TYPES)
export const acmTypes: AcmType[] = loadState(`${KEY}_acm`, SEED_ACM_TYPES)
export const configAudit: ConfigAuditEntry[] = loadState(`${KEY}_audit`, SEED_CONFIG_AUDIT)

export function commit(): void {
  saveState(`${KEY}_building`, buildingTypes)
  saveState(`${KEY}_acm`, acmTypes)
  saveState(`${KEY}_audit`, configAudit)
}
