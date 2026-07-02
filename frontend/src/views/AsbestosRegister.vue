<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useColumnResize } from '@/composables/useColumnResize'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseMultiSelect from '@/components/base/BaseMultiSelect.vue'
import RagBadge from '@/components/base/RagBadge.vue'
import Pagination from '@/components/base/Pagination.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import ConfigurationTab from '@/components/configuration/ConfigurationTab.vue'
import AddSiteModal from '@/components/register/AddSiteModal.vue'
import BulkUploadModal from '@/components/register/BulkUploadModal.vue'
import * as reg from '@/services/register.service'
import { exportRegister } from '@/services/bulk.service'
import { getRegisterCustomers } from '@/services/register.service'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass } from '@/utils/rag'
import { notify } from '@/utils/notify'
import { useBulkJob } from '@/composables/useBulkJob'
import type { SiteListItem, LookupOption } from '@/types'

const router = useRouter()

// Register table: Customer, Site Name, ACM Entries, Highest Risk, AMP Expiry, Last Updated, Updated By
const { colWidths: regColWidths, startResize: regStartResize } = useColumnResize([180, 200, 140, 120, 140, 130, 140])
const tab = ref<'register' | 'config'>('register')

// Filters
const search = ref('')
const customerIds = ref<string[]>([])
const riskLevels = ref<string[]>([])
const customers = ref<LookupOption[]>([])
const customersLoading = ref(false)
const riskOptions = [
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'LOW', label: 'Low' },
  { value: 'NONE', label: 'None' },
]

// Data
const rows = ref<SiteListItem[]>([])
const totalCount = ref(0)
const pageIndex = ref(0)
const pageSize = ref(10)
const loading = ref(true)

// Sort state. Default: Last Updated (newest first) — no sort on AMP Expiry until
// the user clicks that column header.
const sortBy = ref<'ampExpiry' | 'lastUpdated'>('lastUpdated')
const sortDir = ref<'asc' | 'desc'>('desc')

const showAddSite = ref(false)
const showBulk = ref(false)

const bulk = useBulkJob()

// Open modal when topbar pill is clicked from anywhere in the app.
watch(bulk.openModalRequest, () => { showBulk.value = true })

// Reload the register list after a successful bulk import.
bulk.onImported(load)

let loadSeq = 0
async function load() {
  const seq = ++loadSeq
  loading.value = true
  try {
    const res = await reg.getRegister({
      search: search.value,
      customerIds: customerIds.value,
      riskLevels: riskLevels.value as any,
      sortBy: sortBy.value,
      sortDir: sortDir.value,
      pageIndex: pageIndex.value,
      pageSize: pageSize.value,
    })
    if (seq !== loadSeq) return // stale — a newer call is in-flight
    rows.value = res.items
    totalCount.value = res.totalCount
  } catch {
    if (seq !== loadSeq) return
    notify.error('Failed to load the register. Please try again.')
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function toggleAmpSort() {
  // First click activates AMP Expiry sort (ascending); subsequent clicks toggle.
  if (sortBy.value !== 'ampExpiry') {
    sortBy.value = 'ampExpiry'
    sortDir.value = 'asc'
  } else {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  }
  pageIndex.value = 0
  load()
}

function runSearch() {
  pageIndex.value = 0
  load()
}

// Server-side customer search (debounced by BaseMultiSelect). Empty term reloads
// the default first page of customers.
async function onCustomerSearch(term: string) {
  customersLoading.value = true
  try {
    const results = await getRegisterCustomers(term)
    // Keep any currently-selected customers in the list so their label still
    // shows in the summary even when filtered out by the search term.
    const selected = customers.value.filter((c) => customerIds.value.includes(c.id))
    const merged = new Map(results.map((c) => [c.id, c]))
    selected.forEach((c) => { if (!merged.has(c.id)) merged.set(c.id, c) })
    customers.value = [...merged.values()]
  } catch {
    customers.value = []
  } finally {
    customersLoading.value = false
  }
}
function resetFilters() {
  search.value = ''
  customerIds.value = []
  riskLevels.value = []
  sortBy.value = 'lastUpdated'
  sortDir.value = 'desc'
  pageIndex.value = 0
  load()
}
function onPage(i: number) {
  pageIndex.value = i
  load()
}
function openSite(row: SiteListItem) {
  router.push({ name: 'site-detail', params: { asbestosSiteId: row.asbestosSiteId } })
}
const exporting = ref(false)
async function onExport() {
  exporting.value = true
  try {
    // Export only the data matching the currently-applied filters.
    await exportRegister({
      search: search.value,
      customerIds: customerIds.value,
      riskLevels: riskLevels.value,
    })
    notify.success('Register exported.')
  } finally {
    exporting.value = false
  }
}
function onSiteCreated(id: string) {
  showAddSite.value = false
  router.push({ name: 'site-detail', params: { asbestosSiteId: id } })
}

function openPortalPreview() {
  // Preview the read-only Customer Portal view of the first listed site.
  if (!rows.value.length) return
  const url = router.resolve({ name: 'customer-portal-preview', params: { asbestosSiteId: rows.value[0].asbestosSiteId } }).href
  window.open(url, '_blank')
}

onMounted(async () => {
  // Load customers and register in parallel — a slow/failing customers endpoint
  // won't delay the register list from appearing.
  const [c] = await Promise.allSettled([getRegisterCustomers(), load()])
  if (c.status === 'fulfilled') customers.value = c.value
})
</script>

<template>
  <div>
    <!-- Breadcrumb -->
    <nav class="mb-1 text-sm text-jl-teal">
      <span>Settings</span> / <span>Library</span> / <span class="text-jl-navy">Asbestos Register</span>
    </nav>

    <div class="mb-4 flex items-start justify-between">
      <h1 class="text-2xl font-bold text-jl-navy">Asbestos Register</h1>
      <BaseButton variant="secondary" size="sm" :disabled="!rows.length" @click="openPortalPreview"><BaseIcon name="external" :size="14" /> Customer Portal Preview</BaseButton>
    </div>

    <!-- Top tabs -->
    <div class="mb-5 flex gap-6 border-b border-slate-200 text-sm font-semibold">
      <button class="-mb-px border-b-2 pb-3" :class="tab === 'register' ? 'border-jl-teal text-jl-navy' : 'border-transparent text-slate-400'" @click="tab = 'register'">Register</button>
      <button class="-mb-px border-b-2 pb-3" :class="tab === 'config' ? 'border-jl-teal text-jl-navy' : 'border-transparent text-slate-400'" @click="tab = 'config'">Configuration</button>
    </div>

    <!-- REGISTER TAB -->
    <template v-if="tab === 'register'">
      <!-- Filter bar -->
      <div class="jl-card mb-4 p-4">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label class="jl-label">Search</label>
            <div class="relative">
              <span class="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                <BaseIcon name="search" :size="16" />
              </span>
              <input v-model="search" class="jl-input pl-9" placeholder="Site Name / Customer" @keyup.enter="runSearch" />
            </div>
          </div>
          <div>
            <label class="jl-label">Customer</label>
            <BaseMultiSelect
              v-model="customerIds"
              :options="customers.map((c) => ({ value: c.id, label: c.name }))"
              :remote="true"
              :loading="customersLoading"
              @search="onCustomerSearch"
            />
          </div>
          <div>
            <label class="jl-label">Risk Level</label>
            <BaseMultiSelect v-model="riskLevels" :options="riskOptions" :searchable="false" />
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-3">
          <BaseButton variant="orange" @click="resetFilters"><BaseIcon name="reset" :size="15" /> Reset Filter</BaseButton>
          <BaseButton variant="dark" :loading="loading" @click="runSearch"><BaseIcon v-if="!loading" name="search" :size="15" /> Search</BaseButton>
        </div>
      </div>

      <!-- Actions row -->
      <div class="mb-3 flex items-center justify-between">
        <p class="font-bold text-jl-navy">{{ totalCount }} sites in register</p>
        <div class="flex gap-2">
          <BaseButton variant="secondary" :loading="exporting" @click="onExport"><BaseIcon v-if="!exporting" name="download" :size="15" /> Export</BaseButton>
          <BaseButton variant="secondary" @click="showBulk = true"><BaseIcon name="upload" :size="15" /> Bulk Upload</BaseButton>
          <BaseButton @click="showAddSite = true"><BaseIcon name="plus" :size="15" /> Add New Site</BaseButton>
        </div>
      </div>

      <!-- Table -->
      <div class="jl-card overflow-x-auto">
        <table class="text-sm" style="table-layout: fixed; width: 100%; min-width: max-content">
          <colgroup>
            <col v-for="(w, i) in regColWidths" :key="i" :style="{ width: w + 'px' }" />
          </colgroup>
          <thead class="bg-white text-left text-xs font-bold uppercase tracking-wide text-jl-navy">
            <tr class="border-b border-slate-100">
              <th class="relative select-none px-4 py-3">
                Customer
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="regStartResize($event, 0)" />
              </th>
              <th class="relative select-none px-4 py-3">
                Site Name
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="regStartResize($event, 1)" />
              </th>
              <th class="relative select-none px-4 py-3">
                ACM Entries
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="regStartResize($event, 2)" />
              </th>
              <th class="relative select-none px-4 py-3">
                Highest Risk
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="regStartResize($event, 3)" />
              </th>
              <th class="relative cursor-pointer select-none px-4 py-3 hover:text-jl-navy" @click="toggleAmpSort">
                AMP Expiry
                <span v-if="sortBy === 'ampExpiry'" class="ml-1">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
                <span v-else class="ml-1 text-slate-300">↕</span>
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent.stop="regStartResize($event, 4)" />
              </th>
              <th class="relative select-none px-4 py-3">
                Last Updated
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="regStartResize($event, 5)" />
              </th>
              <th class="px-4 py-3">Updated By</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="r in rows" :key="r.asbestosSiteId" class="cursor-pointer hover:bg-slate-50/60" @click="openSite(r)">
              <td class="overflow-hidden px-4 py-3 text-slate-600">
                <span class="block truncate" :title="r.customerName">{{ r.customerName }}</span>
              </td>
              <td class="overflow-hidden px-4 py-3">
                <span class="block truncate font-semibold text-jl-teal hover:underline" :title="r.siteName">{{ r.siteName }}</span>
              </td>
              <td class="overflow-hidden px-4 py-3 text-slate-600">{{ r.totalAcm }} ({{ r.activeAcm }} active)</td>
              <td class="px-4 py-3"><RagBadge :risk="r.highestRisk" /></td>
              <td class="overflow-hidden px-4 py-3">
                <span v-if="r.ampExpiryDate" class="inline-flex items-center gap-2 font-semibold" :class="ragTextClass(r.ampExpiryRag)">
                  <span class="h-2 w-2 rounded-full" :class="ragDotClass(r.ampExpiryRag)" />
                  {{ formatDate(r.ampExpiryDate) }}
                </span>
                <span v-else class="text-slate-400">— —</span>
              </td>
              <td class="overflow-hidden px-4 py-3 text-slate-600">{{ formatDate(r.lastUpdated) }}</td>
              <td class="overflow-hidden px-4 py-3 text-slate-600">
                <span class="block truncate" :title="r.updatedByName">{{ r.updatedByName }}</span>
              </td>
            </tr>
            <tr v-if="loading">
              <td colspan="7"><LoadingState message="Loading register…" /></td>
            </tr>
            <tr v-else-if="!rows.length">
              <td colspan="7" class="px-4 py-10 text-center text-slate-400">No sites match your filters.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <Pagination :page-index="pageIndex" :page-size="pageSize" :total-count="totalCount" @update:page-index="onPage" />
    </template>

    <!-- CONFIGURATION TAB -->
    <ConfigurationTab v-else />

    <!-- Modals -->
    <AddSiteModal v-if="showAddSite" @close="showAddSite = false" @created="onSiteCreated" />
    <BulkUploadModal v-if="showBulk" @close="showBulk = false" />
  </div>
</template>
