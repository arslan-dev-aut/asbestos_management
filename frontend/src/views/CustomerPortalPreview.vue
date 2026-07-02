<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseSelect from '@/components/base/BaseSelect.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import RagBadge from '@/components/base/RagBadge.vue'
import Pagination from '@/components/base/Pagination.vue'
import AcmEntriesTable from '@/components/register/AcmEntriesTable.vue'
import { getPortalSiteList, getSiteFull, getAcmEntriesPaged } from '@/services/register.service'
import { viewDocument, downloadDocument, viewAttachment, downloadAttachment } from '@/services/documents.service'
import { notify } from '@/utils/notify'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass, highestRisk } from '@/utils/rag'
import { docTypeLabel, PAGE_SIZE } from '@/utils/const'
import type { ReadonlySiteData, LookupOption, SiteDocument } from '@/types'

const props = defineProps<{ asbestosSiteId: string }>()
const router = useRouter()

const data = ref<ReadonlySiteData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const docLoadingId = ref<string | null>(null)
const attLoadingId = ref<string | null>(null)
const pageIndex = ref(0)
const acmTotalCount = ref(0)

const siteList = ref<LookupOption[]>([])
const siteListLoading = ref(true)
const selectedSiteId = ref<string | null>(null)
const activeSiteId = ref<string>('')

const highestActiveRisk = computed(() =>
  highestRisk((data.value?.acmEntries ?? []).filter((e) => e.status === 'ACTIVE').map((e) => e.riskScore)),
)
const activeCount = computed(() => (data.value?.acmEntries ?? []).filter((e) => e.status === 'ACTIVE').length)

async function loadSite(id: string) {
  if (!id) return
  loading.value = true
  error.value = null
  data.value = null
  pageIndex.value = 0
  acmTotalCount.value = 0
  try {
    const full = await getSiteFull(id)
    data.value = {
      siteName: full.site.siteName,
      customerName: full.site.customerName,
      acmEntries: full.acmEntries,
      documents: full.documents.filter((d) => d.docType !== 'AMP' || d.isCurrentAmp),
    }
    acmTotalCount.value = full.acmTotalCount
    activeSiteId.value = id
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
      ?? (e as { message?: string })?.message
      ?? 'Failed to load site data.'
    error.value = msg
    notify.error(msg)
  } finally {
    loading.value = false
  }
}

async function loadAcmPage(page: number) {
  if (!activeSiteId.value) return
  pageIndex.value = page
  loading.value = true
  try {
    const result = await getAcmEntriesPaged(activeSiteId.value, { page, pageSize: PAGE_SIZE, statusFilter: 'all' })
    if (data.value) data.value = { ...data.value, acmEntries: result.items }
    acmTotalCount.value = result.totalCount
  } catch {
    notify.error('Failed to load ACM entries.')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  siteListLoading.value = true
  try {
    siteList.value = await getPortalSiteList()
  } catch {
    notify.error('Could not load site list.')
  } finally {
    siteListLoading.value = false
  }
  const initialId = siteList.value.find((s) => s.id === props.asbestosSiteId)
    ? props.asbestosSiteId
    : (siteList.value[0]?.id ?? props.asbestosSiteId)
  selectedSiteId.value = initialId
  await loadSite(initialId)
})

watch(selectedSiteId, (id) => {
  if (id && id !== activeSiteId.value) loadSite(id)
})

async function onViewDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await viewDocument(activeSiteId.value, d) }
  catch { notify.error('Could not open document.') }
  finally { docLoadingId.value = null }
}
async function onDownloadDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await downloadDocument(activeSiteId.value, d) }
  catch { notify.error('Could not download document.') }
  finally { docLoadingId.value = null }
}

function findAtt(fileName: string) {
  for (const entry of data.value?.acmEntries ?? []) {
    const att = entry.attachments.find((a) => a.fileName === fileName)
    if (att) return { att, acmEntryId: entry.id }
  }
  return null
}
async function onViewAtt(fileName: string) {
  const found = findAtt(fileName)
  if (!found) return
  attLoadingId.value = found.att.id
  try { await viewAttachment(activeSiteId.value, found.acmEntryId, found.att.id, found.att.fileName, found.att.downloadUrl) }
  catch { notify.error('Could not open attachment.') }
  finally { attLoadingId.value = null }
}
async function onDownloadAtt(fileName: string) {
  const found = findAtt(fileName)
  if (!found) return
  attLoadingId.value = found.att.id
  try { await downloadAttachment(activeSiteId.value, found.acmEntryId, found.att.id, found.att.fileName, found.att.downloadUrl) }
  catch { notify.error('Could not download attachment.') }
  finally { attLoadingId.value = null }
}
</script>

<template>
  <div class="min-h-full bg-[#eef1f4]">
    <!-- Customer Portal topbar — always visible -->
    <header class="flex items-center justify-between bg-jl-navy-dark px-6 py-3 text-white">
      <span class="text-xs font-bold uppercase tracking-widest text-slate-300">Customer Portal</span>
      <span class="text-sm font-semibold">Preview</span>
    </header>

    <div class="mx-auto max-w-6xl px-6 py-6">
      <button
        class="mb-4 inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold hover:bg-slate-50"
        @click="router.push('/asbestos-register')"
      >
        ← Back to Register
      </button>

      <!-- Site selector — skeleton while list loads -->
      <div class="mb-5 max-w-sm">
        <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Select Site</label>
        <div v-if="siteListLoading" class="h-9 w-full animate-pulse rounded-md bg-slate-200" />
        <BaseSelect
          v-else
          v-model="selectedSiteId"
          :options="siteList.map((s) => ({ value: s.id, label: s.name }))"
          placeholder="Select a site…"
          :searchable="true"
        />
      </div>

      <!-- Error state -->
      <div v-if="error" class="rounded-md bg-red-50 px-4 py-6 text-center text-sm text-rag-red">{{ error }}</div>

      <template v-else>
        <!-- Breadcrumb — skeleton while loading -->
        <nav class="mb-1 text-sm text-jl-teal">
          <span>Settings</span> / <span>Library</span> / <span>Asbestos Register</span> /
          <span v-if="loading" class="inline-block h-3 w-24 animate-pulse rounded bg-slate-200 align-middle" />
          <span v-else class="inline-block max-w-xs truncate align-bottom text-jl-navy" :title="data?.siteName">{{ data?.siteName }}</span>
        </nav>

        <!-- Header — skeleton while loading -->
        <div class="mb-4 flex items-start justify-between">
          <div>
            <template v-if="loading">
              <div class="mb-2 h-7 w-56 animate-pulse rounded bg-slate-200" />
              <div class="h-4 w-36 animate-pulse rounded bg-slate-100" />
            </template>
            <template v-else>
              <h1 class="max-w-xl truncate text-2xl font-bold text-jl-navy" :title="data?.siteName">{{ data?.siteName }}</h1>
              <p class="max-w-xl truncate text-sm text-slate-500" :title="data?.customerName">{{ data?.customerName }}</p>
            </template>
          </div>
          <div class="flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
            <span class="text-slate-500">Highest active risk</span>
            <span v-if="loading" class="h-5 w-12 animate-pulse rounded bg-slate-200" />
            <RagBadge v-else :risk="highestActiveRisk" />
          </div>
        </div>

        <!-- Site Documents -->
        <section class="jl-card mb-6 p-5">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-lg font-bold text-jl-navy">Site Documents</h2>
          </div>

          <!-- Skeleton rows -->
          <template v-if="loading">
            <div v-for="n in 2" :key="n" class="flex items-center gap-4 border-b border-slate-100 py-3">
              <div class="h-5 w-5 animate-pulse rounded bg-slate-200" />
              <div class="flex-1 space-y-1.5">
                <div class="h-4 w-48 animate-pulse rounded bg-slate-200" />
                <div class="h-3 w-32 animate-pulse rounded bg-slate-100" />
              </div>
              <div class="h-5 w-16 animate-pulse rounded bg-slate-100" />
              <div class="flex gap-1">
                <div class="h-7 w-7 animate-pulse rounded bg-slate-100" />
                <div class="h-7 w-7 animate-pulse rounded bg-slate-100" />
              </div>
            </div>
          </template>
          <div v-else class="divide-y divide-slate-100">
            <div
              v-for="d in data?.documents ?? []"
              :key="d.id"
              class="flex items-center gap-4 py-3"
              :class="{ 'opacity-50': d.docType === 'AMP' && !d.isCurrentAmp }"
            >
              <span class="text-rag-red"><BaseIcon name="file" :size="18" /></span>
              <div class="flex-1">
                <p class="font-semibold text-jl-navy">{{ d.fileName }}</p>
                <p class="text-xs text-slate-400">Uploaded {{ formatDate(d.uploadedAt) }} by {{ d.uploadedByName }}</p>
              </div>
              <span v-if="d.docType === 'AMP' && !d.isCurrentAmp" class="rounded-md bg-slate-200 px-2.5 py-1 text-xs font-bold uppercase text-slate-500">Superseded</span>
              <span v-else class="rounded-md bg-slate-200 px-2.5 py-1 text-xs font-bold text-jl-navy">{{ docTypeLabel(d.docType) }}</span>
              <span v-if="d.docType === 'AMP'" class="inline-flex items-center gap-1.5 text-sm font-semibold" :class="d.isCurrentAmp ? ragTextClass(d.ampExpiryRag ?? 'NONE') : 'text-slate-400'">
                <span v-if="d.isCurrentAmp" class="h-2 w-2 rounded-full" :class="ragDotClass(d.ampExpiryRag ?? 'NONE')" />
                {{ formatDate(d.ampExpiryDate) }}
              </span>
              <div class="flex items-center gap-2 text-slate-600">
                <span v-if="docLoadingId === d.id" class="px-2 text-xs animate-pulse text-slate-400">Loading…</span>
                <template v-else>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="View" @click="onViewDoc(d)"><BaseIcon name="eye" :size="18" :stroke-width="2.2" /></button>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="Download" @click="onDownloadDoc(d)"><BaseIcon name="download" :size="18" :stroke-width="2.2" /></button>
                </template>
              </div>
            </div>
            <p v-if="!(data?.documents ?? []).length" class="py-6 text-center text-sm text-slate-400">No documents uploaded yet.</p>
          </div>
        </section>

        <!-- ACM Entries -->
        <div class="mb-3 flex items-center justify-between">
          <div v-if="loading" class="h-5 w-44 animate-pulse rounded bg-slate-200" />
          <h2 v-else class="font-bold text-jl-navy">{{ acmTotalCount }} ACM entries ({{ activeCount }} active)</h2>
        </div>

        <!-- Skeleton rows -->
        <template v-if="loading">
          <div class="jl-card overflow-hidden">
            <div v-for="n in 4" :key="n" class="flex items-center gap-6 border-b border-slate-100 px-4 py-3 last:border-0">
              <div class="h-4 w-28 animate-pulse rounded bg-slate-200" />
              <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
              <div class="h-4 w-20 animate-pulse rounded bg-slate-200" />
              <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
              <div class="h-5 w-14 animate-pulse rounded bg-slate-100" />
              <div class="ml-auto flex gap-2">
                <div class="h-7 w-7 animate-pulse rounded bg-slate-100" />
                <div class="h-7 w-7 animate-pulse rounded bg-slate-100" />
              </div>
            </div>
          </div>
        </template>
        <template v-else>
          <AcmEntriesTable
            :entries="data?.acmEntries ?? []"
            variant="readonly"
            :loading-attachment-id="attLoadingId"
            @view-attachment="(name) => onViewAtt(name)"
            @download-attachment="(name) => onDownloadAtt(name)"
          />
          <Pagination
            :page-index="pageIndex"
            :page-size="PAGE_SIZE"
            :total-count="acmTotalCount"
            @update:page-index="loadAcmPage($event)"
          />
        </template>
      </template>
    </div>
  </div>
</template>
