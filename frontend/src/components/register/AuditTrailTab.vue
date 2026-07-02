<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Pagination from '@/components/base/Pagination.vue'
import BaseMultiSelect from '@/components/base/BaseMultiSelect.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { getSiteAudit } from '@/services/audit.service'
import { getBuildingTypes, getAcmTypes } from '@/services/configuration.service'
import { formatDateTime } from '@/utils/format'
import {
  auditTypeLabels, actionsByType, actionLabels, auditTypeDot,
  type AuditType,
} from '@/utils/auditTaxonomy'
import { conditionLabel, riskLabel } from '@/utils/const'
import { notify } from '@/utils/notify'
import type { AuditLogEntry } from '@/types'

const props = defineProps<{ asbestosSiteId: string }>()

const entries = ref<AuditLogEntry[]>([])
const totalCount = ref(0)
const loading = ref(true)
const expanded = ref<Set<string>>(new Set())

// Filters: Audit Type → Action (dependent), both multi-select. Configuration
// audit lives in the Configuration page's own audit tab, so it's excluded here.
const auditTypes = ref<AuditType[]>([])
const actions = ref<string[]>([])

const auditTypeOptions = (Object.keys(auditTypeLabels) as AuditType[])
  .filter((t) => t !== 'CONFIGURATION')
  .map((t) => ({ value: t, label: auditTypeLabels[t] }))
// Action options are the human-readable labels for the selected audit types
// (or all types when none selected). De-duplicated.
const actionOptions = computed(() => {
  const types = auditTypes.value.length
    ? auditTypes.value
    : (Object.keys(actionsByType) as AuditType[]).filter((t) => t !== 'CONFIGURATION')
  const labels = new Set<string>()
  types.forEach((t) => actionsByType[t].forEach((a) => labels.add(actionLabels[a])))
  return [...labels].map((l) => ({ value: l, label: l }))
})

const pageIndex = ref(0)
const pageSize = 10

// ID → name maps for resolving GUIDs in the expanded detail view.
const buildingTypeNames = ref<Record<string, string>>({})
const acmTypeNames = ref<Record<string, string>>({})

async function loadLookups() {
  try {
    const [bts, acms] = await Promise.all([getBuildingTypes(), getAcmTypes()])
    buildingTypeNames.value = Object.fromEntries(bts.map((b) => [b.id, b.name]))
    acmTypeNames.value = Object.fromEntries(acms.map((a) => [a.id, a.name]))
  } catch {
    // Non-fatal — detail view falls back to showing raw IDs.
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getSiteAudit(props.asbestosSiteId, {
      pageIndex: pageIndex.value,
      pageSize,
      auditTypes: auditTypes.value,
      actions: actions.value,
    })
    entries.value = res.items
    totalCount.value = res.totalCount
  } catch {
    notify.error('Failed to load audit trail.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLookups()
  load()
})

// Changing audit types prunes any selected actions that are no longer valid,
// then resets to page 0 and refetches. A flag prevents the action watcher from
// firing a second load when the prune itself mutates `actions`. Both watchers
// debounce 300ms so rapid multi-select changes don't fire many requests.
let suppressActionWatch = false
let auditDebounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedLoad() {
  if (auditDebounceTimer) clearTimeout(auditDebounceTimer)
  auditDebounceTimer = setTimeout(() => { pageIndex.value = 0; load() }, 300)
}
watch(auditTypes, () => {
  const valid = new Set(actionOptions.value.map((o) => o.value))
  const pruned = actions.value.filter((a) => valid.has(a))
  suppressActionWatch = pruned.length !== actions.value.length
  actions.value = pruned
  debouncedLoad()
  suppressActionWatch = false
})
watch(actions, () => {
  if (suppressActionWatch) return
  debouncedLoad()
})

function goToPage(p: number) {
  pageIndex.value = p
  load()
}

function toggle(id: string) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
function resetFilters() {
  if (!auditTypes.value.length && !actions.value.length) return // nothing to reset
  // Clearing audit types triggers its watcher (prunes actions + reloads). If only
  // actions were set, clear them directly.
  if (auditTypes.value.length) auditTypes.value = []
  else actions.value = []
}

function prettyKey(k: string) {
  const base = k.replace(/Id$/, '')
  return base.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase()).trim()
}

// Keys that are internal IDs — skip rendering them in the detail panel.
const SKIP_KEYS = new Set(['acmEntryId', 'documentId', 'attachmentId'])

// Resolve known IDs / coded values to human-readable text for the detail view.
function prettyValue(key: string, value: unknown): string {
  const v = value == null ? '' : String(value)
  if (!v) return '—'
  if (key === 'buildingTypeId') return buildingTypeNames.value[v] ?? v
  if (key === 'acmTypeId') return acmTypeNames.value[v] ?? v
  if (key === 'condition') return conditionLabel(v as never) ?? v
  if (key === 'riskScore') return riskLabel(v as never) ?? v
  return v
}

// "changes" is { fieldName: { from, to } } — flatten into display rows.
interface ChangeRow { field: string; from: string; to: string }
function expandChanges(changes: unknown): ChangeRow[] {
  if (!changes || typeof changes !== 'object') return []
  return Object.entries(changes as Record<string, { from: unknown; to: unknown }>).map(([field, diff]) => ({
    field: prettyKey(field),
    from: prettyValue(field, diff.from),
    to: prettyValue(field, diff.to),
  }))
}
</script>

<template>
  <div>
  <!-- Filters -->
  <div class="jl-card mb-4 p-4">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div>
        <label class="jl-label">Audit Type</label>
        <BaseMultiSelect v-model="auditTypes" :options="auditTypeOptions" placeholder="All audit types" />
      </div>
      <div>
        <label class="jl-label">Action</label>
        <BaseMultiSelect v-model="actions" :options="actionOptions" placeholder="All actions" />
      </div>
      <div class="flex items-end">
        <button class="text-sm font-semibold text-jl-teal hover:underline" @click="resetFilters">Reset filters</button>
      </div>
    </div>
  </div>

  <!-- Trail -->
  <div class="jl-card overflow-hidden">
    <div class="grid grid-cols-[180px_140px_1fr_40px] bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
      <span>Date / Time</span><span>User</span><span>Action</span><span></span>
    </div>
    <LoadingState v-if="loading" message="Loading audit trail…" />
    <div v-else class="divide-y divide-slate-100">
      <div v-for="e in entries" :key="e.id">
        <button class="grid w-full grid-cols-[180px_140px_1fr_40px] items-center px-4 py-3 text-left text-sm hover:bg-slate-50/60" @click="toggle(e.id)">
          <span class="text-slate-600">{{ formatDateTime(e.occurredAt) }}</span>
          <span class="truncate text-slate-600" :title="e.userName">{{ e.userName }}</span>
          <span class="flex min-w-0 items-center">
            <span class="inline-flex min-w-0 items-center gap-2 font-semibold text-jl-navy">
              <span class="h-2 w-2 shrink-0 rounded-full" :class="auditTypeDot[e.auditType]" />
              <span class="truncate" :title="e.action">{{ e.action }}</span>
            </span>
            <span class="ml-2 shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{{ auditTypeLabels[e.auditType] }}</span>
          </span>
          <span class="text-slate-400 transition" :class="{ 'rotate-180': expanded.has(e.id) }">▾</span>
        </button>
        <!-- Expanded "Detail Captured" -->
        <div v-if="expanded.has(e.id)" class="bg-slate-50/70 px-6 py-3 text-sm">
          <template v-if="Object.keys(e.details).length">
            <!-- "changes" block: render as a from → to table -->
            <template v-if="e.details.changes && typeof e.details.changes === 'object'">
              <p class="mb-1 font-semibold text-slate-500">Changes</p>
              <table class="mb-3 w-full text-xs">
                <thead>
                  <tr class="text-left text-slate-400">
                    <th class="pb-1 pr-4 font-medium">Field</th>
                    <th class="pb-1 pr-4 font-medium">From</th>
                    <th class="pb-1 font-medium">To</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="row in expandChanges(e.details.changes)" :key="row.field">
                    <td class="py-1 pr-4 font-medium text-slate-500">{{ row.field }}</td>
                    <td class="py-1 pr-4 text-rag-red line-through">{{ row.from }}</td>
                    <td class="py-1 text-rag-green font-semibold">{{ row.to }}</td>
                  </tr>
                </tbody>
              </table>
            </template>
            <!-- Remaining scalar fields (skip internal IDs and "changes" itself) -->
            <dl class="grid grid-cols-[200px_1fr] gap-y-1">
              <template v-for="(value, key) in e.details" :key="key">
                <dt v-if="key !== 'changes' && !SKIP_KEYS.has(String(key)) && typeof value !== 'object'" class="font-medium text-slate-500">{{ prettyKey(String(key)) }}</dt>
                <dd v-if="key !== 'changes' && !SKIP_KEYS.has(String(key)) && typeof value !== 'object'" class="truncate text-jl-navy" :title="prettyValue(String(key), value)">{{ prettyValue(String(key), value) }}</dd>
              </template>
            </dl>
          </template>
          <p v-else class="text-slate-400">No additional detail captured.</p>
        </div>
      </div>
      <p v-if="!entries.length" class="px-4 py-10 text-center text-slate-400">No audit entries match these filters.</p>
    </div>
  </div>
  <Pagination :page-index="pageIndex" :page-size="pageSize" :total-count="totalCount" @update:page-index="goToPage($event)" />
  </div>
</template>
