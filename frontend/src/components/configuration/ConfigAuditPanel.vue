<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatDateTime } from '@/utils/format'
import Pagination from '@/components/base/Pagination.vue'
import type { ConfigAuditEntry, ConfigAuditAction } from '@/types'

const props = defineProps<{ entries: ConfigAuditEntry[] }>()

const pageIndex = ref(0)
const PAGE_SIZE = 10

const sorted = computed(() => [...props.entries].sort((a, b) => (b.occurredAt > a.occurredAt ? 1 : -1)))
const page = computed(() => sorted.value.slice(pageIndex.value * PAGE_SIZE, (pageIndex.value + 1) * PAGE_SIZE))

const actionLabel: Record<ConfigAuditAction, string> = {
  TYPE_ADDED: 'Added',
  TYPE_ACTIVATED: 'Activated',
  TYPE_DEACTIVATED: 'Deactivated',
}
const dotClass: Record<ConfigAuditAction, string> = {
  TYPE_ADDED: 'bg-rag-green',
  TYPE_ACTIVATED: 'bg-jl-teal',
  TYPE_DEACTIVATED: 'bg-rag-amber',
}
const categoryLabel = (c: ConfigAuditEntry['category']) => (c === 'BUILDING_TYPE' ? 'Building Type' : 'ACM Type')
</script>

<template>
  <div>
  <div class="jl-card overflow-hidden">
    <table class="w-full text-sm">
      <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
        <tr>
          <th class="px-4 py-3">Date / Time</th>
          <th class="px-4 py-3">User</th>
          <th class="px-4 py-3">Category</th>
          <th class="px-4 py-3">Action</th>
          <th class="px-4 py-3">Type</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        <tr v-for="e in page" :key="e.id" class="hover:bg-slate-50/60">
          <td class="px-4 py-3 text-slate-600">{{ formatDateTime(e.occurredAt) }}</td>
          <td class="px-4 py-3 text-slate-600">{{ e.userName }}</td>
          <td class="px-4 py-3 text-slate-600">{{ categoryLabel(e.category) }}</td>
          <td class="px-4 py-3">
            <span class="inline-flex items-center gap-2 font-semibold text-jl-navy">
              <span class="h-2 w-2 rounded-full" :class="dotClass[e.action]" />
              {{ actionLabel[e.action] }}
            </span>
          </td>
          <td class="px-4 py-3 font-medium text-jl-navy">{{ e.typeName }}</td>
        </tr>
        <tr v-if="!sorted.length">
          <td colspan="5" class="px-4 py-6 text-center text-slate-400">No configuration history yet.</td>
        </tr>
      </tbody>
    </table>
  </div>
  <Pagination :page-index="pageIndex" :page-size="PAGE_SIZE" :total-count="sorted.length" @update:page-index="pageIndex = $event" />
  </div>
</template>
