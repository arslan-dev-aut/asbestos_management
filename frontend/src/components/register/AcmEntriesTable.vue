<script setup lang="ts">
import { computed } from 'vue'
import RagBadge from '@/components/base/RagBadge.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import NotesCell from '@/components/base/NotesCell.vue'
import { conditionLabel } from '@/utils/const'
import { formatDate } from '@/utils/format'
import { useColumnResize } from '@/composables/useColumnResize'
import type { AcmEntry } from '@/types'

const props = withDefaults(
  defineProps<{
    entries: AcmEntry[]
    variant?: 'admin' | 'readonly'
    hideAsset?: boolean
    loadingAttachmentId?: string | null
    togglingId?: string | null
  }>(),
  { variant: 'admin', hideAsset: false, loadingAttachmentId: null, togglingId: null },
)
const emit = defineEmits<{
  view: [AcmEntry]
  edit: [AcmEntry]
  toggleStatus: [AcmEntry]
  viewAttachment: [name: string, fileKey?: string | null]
  downloadAttachment: [name: string, fileKey?: string | null]
}>()

const isAdmin = () => props.variant === 'admin'
// Base 7 columns + optional Asset + (admin: Last Updated, Updated By) + trailing Actions/Documents.
const colCount = () => 7 + (props.hideAsset ? 0 : 1) + (isAdmin() ? 2 : 0) + 1

// Default widths: Building, Room, [Asset], ACM Type, Condition, Risk, Notes, Status,
// [admin: Last Updated, Updated By], Actions or Documents
const defaultWidths = computed(() => {
  const base = [144, 176, 144, 120, 100, 176, 120]
  if (!props.hideAsset) base.splice(2, 0, 144) // Asset column
  if (isAdmin()) base.push(140, 140)            // Last Updated, Updated By
  base.push(200)                                // Actions or Documents
  return base
})

const { colWidths, startResize } = useColumnResize(defaultWidths.value)
</script>

<template>
  <div class="jl-card overflow-x-auto">
    <table class="text-sm" style="table-layout: fixed; width: 100%; min-width: max-content">
      <colgroup>
        <col v-for="(w, i) in colWidths" :key="i" :style="{ width: w + 'px' }" />
      </colgroup>
      <thead class="bg-white text-left text-xs font-bold uppercase tracking-wide text-jl-navy">
        <tr class="border-b border-slate-100">
          <!-- Building -->
          <th class="relative select-none px-4 py-3">
            Building
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, 0)" />
          </th>
          <!-- Room / Location -->
          <th class="relative select-none px-4 py-3">
            Room / Location
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 1 : 1)" />
          </th>
          <!-- Asset (optional) -->
          <th v-if="!hideAsset" class="relative select-none px-4 py-3">
            Asset
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, 2)" />
          </th>
          <!-- ACM Type -->
          <th class="relative select-none px-4 py-3">
            ACM Type
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 2 : 3)" />
          </th>
          <!-- Condition -->
          <th class="relative select-none px-4 py-3">
            Condition
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 3 : 4)" />
          </th>
          <!-- Risk Score -->
          <th class="relative select-none px-4 py-3">
            Risk Score
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 4 : 5)" />
          </th>
          <!-- Notes -->
          <th class="relative select-none px-4 py-3">
            Notes
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 5 : 6)" />
          </th>
          <!-- Status -->
          <th class="relative select-none px-4 py-3">
            Status
            <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 6 : 7)" />
          </th>
          <!-- Last Updated / Updated By — admin only -->
          <template v-if="isAdmin()">
            <th class="relative select-none px-4 py-3">
              Last Updated
              <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 7 : 8)" />
            </th>
            <th class="relative select-none px-4 py-3">
              Updated By
              <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="startResize($event, hideAsset ? 8 : 9)" />
            </th>
          </template>
          <!-- Actions / Documents — no resize handle (last column) -->
          <th class="px-4 py-3">{{ isAdmin() ? 'Actions' : 'Documents' }}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        <tr v-for="e in entries" :key="e.id" class="hover:bg-slate-50/60">
          <td class="overflow-hidden px-4 py-3 text-slate-600">
            <span class="block truncate" :title="e.buildingTypeName">{{ e.buildingTypeName }}</span>
          </td>
          <td class="overflow-hidden px-4 py-3 text-slate-600">
            <span class="inline-flex items-center gap-1.5">
              <span class="truncate" :title="e.roomLocation">{{ e.roomLocation }}</span>
              <span v-if="e.attachments.length" class="inline-flex shrink-0 items-center gap-0.5 text-xs text-jl-teal" :title="`${e.attachments.length} attachment(s)`">
                <BaseIcon name="paperclip" :size="13" /> {{ e.attachments.length }}
              </span>
            </span>
          </td>
          <td v-if="!hideAsset" class="overflow-hidden px-4 py-3 text-slate-600">
            <span class="inline-flex items-center gap-1">
              <span class="truncate" :class="e.assetName ? '' : 'text-slate-400'" :title="e.assetName ?? undefined">{{ e.assetName ?? '—' }}</span>
              <span v-if="e.assetDiscrepancy" class="cursor-help shrink-0 text-jl-orange" title="Asset no longer active on this site — please review.">⚠</span>
            </span>
          </td>
          <td class="overflow-hidden px-4 py-3 text-slate-600">
            <span class="block truncate" :title="e.acmTypeName">{{ e.acmTypeName }}</span>
          </td>
          <td class="overflow-hidden px-4 py-3 text-slate-600">{{ conditionLabel(e.condition) }}</td>
          <td class="px-4 py-3"><RagBadge :risk="e.riskScore" /></td>
          <td class="overflow-hidden px-4 py-3"><NotesCell :notes="e.notes" /></td>
          <td class="overflow-hidden px-4 py-3">
            <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold" :class="e.status === 'ACTIVE' ? 'bg-rag-green-bg text-jl-green-dark' : 'bg-rag-grey-bg text-slate-500'">
              <span class="h-1.5 w-1.5 rounded-full" :class="e.status === 'ACTIVE' ? 'bg-rag-green' : 'bg-slate-400'" />
              {{ e.status === 'ACTIVE' ? 'Active' : 'Remediated' }}
            </span>
          </td>

          <!-- Last Updated / Updated By — admin only -->
          <template v-if="isAdmin()">
            <td class="overflow-hidden px-4 py-3 text-slate-600">{{ e.updatedAt ? formatDate(e.updatedAt) : '—' }}</td>
            <td class="overflow-hidden px-4 py-3 text-slate-600">
              <span class="block truncate" :title="e.updatedByName ?? ''">{{ e.updatedByName ?? '—' }}</span>
            </td>
          </template>

          <template v-if="isAdmin()">
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <button class="inline-flex items-center gap-1.5 rounded-md p-1.5 text-jl-teal transition-colors hover:bg-jl-teal/10" title="View" @click="emit('view', e)"><BaseIcon name="eye" :size="16" /></button>
                <button class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold text-jl-navy shadow-sm transition-colors hover:bg-slate-50" @click="emit('edit', e)">
                  <BaseIcon name="pencil" :size="16" /> Edit
                </button>
                <button
                  class="inline-flex items-center gap-1.5 text-jl-teal hover:underline disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="togglingId === e.id"
                  @click="emit('toggleStatus', e)"
                >
                  <span v-if="togglingId === e.id" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  {{ togglingId === e.id ? 'Updating…' : (e.status === 'ACTIVE' ? 'Mark Remediated' : 'Reactivate') }}
                </button>
              </div>
            </td>
          </template>

          <td v-else class="overflow-hidden px-4 py-3">
            <div v-if="e.attachments.length" class="space-y-1">
              <div v-for="att in e.attachments" :key="att.id" class="flex items-center gap-2">
                <span class="text-jl-teal"><BaseIcon name="paperclip" :size="15" /></span>
                <span class="truncate text-xs text-slate-600" :title="att.fileName">{{ att.fileName }}</span>
                <span v-if="loadingAttachmentId === att.id" class="text-xs text-slate-400 animate-pulse">Loading…</span>
                <template v-else>
                  <button class="rounded p-1 text-slate-600 transition-colors hover:text-jl-teal" title="View" @click="emit('viewAttachment', att.fileName, att.fileKey)"><BaseIcon name="eye" :size="18" :stroke-width="2.2" /></button>
                  <button class="rounded p-1 text-slate-600 transition-colors hover:text-jl-teal" title="Download" @click="emit('downloadAttachment', att.fileName, att.fileKey)"><BaseIcon name="download" :size="18" :stroke-width="2.2" /></button>
                </template>
              </div>
            </div>
            <span v-else class="text-slate-400">—</span>
          </td>
        </tr>
        <tr v-if="!entries.length">
          <td :colspan="colCount()" class="px-4 py-10 text-center text-slate-400">No ACM entries.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
