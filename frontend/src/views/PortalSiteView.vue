<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import RagBadge from '@/components/base/RagBadge.vue'
import Pagination from '@/components/base/Pagination.vue'
import AcmEntriesTable from '@/components/register/AcmEntriesTable.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { getSiteFull, getAcmEntriesPaged } from '@/services/register.service'
import { viewDocument, downloadDocument, viewAttachment, downloadAttachment } from '@/services/documents.service'
import { notify } from '@/utils/notify'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass, highestRisk } from '@/utils/rag'
import { docTypeLabel, PAGE_SIZE } from '@/utils/const'
import type { ReadonlySiteData, SiteDocument } from '@/types'

const props = defineProps<{ asbestosSiteId: string }>()

const data = ref<ReadonlySiteData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const docLoadingId = ref<string | null>(null)
const attLoadingId = ref<string | null>(null)
const pageIndex = ref(0)
const acmTotalCount = ref(0)

const highestActiveRisk = computed(() =>
  highestRisk((data.value?.acmEntries ?? []).filter((e) => e.status === 'ACTIVE').map((e) => e.riskScore)),
)
const activeCount = computed(() => (data.value?.acmEntries ?? []).filter((e) => e.status === 'ACTIVE').length)
const hasEntries = computed(() => acmTotalCount.value > 0)

onMounted(async () => {
  loading.value = true
  error.value = null
  try {
    const full = await getSiteFull(props.asbestosSiteId)
    data.value = {
      siteName: full.site.siteName,
      customerName: full.site.customerName,
      acmEntries: full.acmEntries,
      documents: full.documents.filter((d) => d.docType !== 'AMP' || d.isCurrentAmp),
    }
    acmTotalCount.value = full.acmTotalCount
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      (e as { message?: string })?.message ??
      'Failed to load site data.'
    error.value = msg
  } finally {
    loading.value = false
  }
})

async function loadAcmPage(page: number) {
  pageIndex.value = page
  try {
    const result = await getAcmEntriesPaged(props.asbestosSiteId, { page, pageSize: PAGE_SIZE, statusFilter: 'all' })
    if (data.value) data.value = { ...data.value, acmEntries: result.items }
    acmTotalCount.value = result.totalCount
  } catch {
    notify.error('Failed to load ACM entries.')
  }
}

async function onViewDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await viewDocument(props.asbestosSiteId, d) }
  catch { notify.error('Could not open document.') }
  finally { docLoadingId.value = null }
}
async function onDownloadDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await downloadDocument(props.asbestosSiteId, d) }
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
  try { await viewAttachment(props.asbestosSiteId, found.acmEntryId, found.att.id, found.att.fileName, found.att.downloadUrl) }
  catch { notify.error('Could not open attachment.') }
  finally { attLoadingId.value = null }
}
async function onDownloadAtt(fileName: string) {
  const found = findAtt(fileName)
  if (!found) return
  attLoadingId.value = found.att.id
  try { await downloadAttachment(props.asbestosSiteId, found.acmEntryId, found.att.id, found.att.fileName, found.att.downloadUrl) }
  catch { notify.error('Could not download attachment.') }
  finally { attLoadingId.value = null }
}
</script>

<template>
  <div class="min-h-full bg-[#eef1f4] px-6 py-6">
    <!-- Loading -->
    <LoadingState v-if="loading" message="Loading asbestos register…" />

    <!-- Error -->
    <div v-else-if="error" class="rounded-md bg-red-50 px-4 py-8 text-center text-sm text-rag-red">{{ error }}</div>

    <template v-else-if="data">
      <!-- Site header -->
      <div class="mb-5 flex items-start justify-between">
        <div>
          <h1 class="max-w-xl truncate text-2xl font-bold text-jl-navy" :title="data.siteName">{{ data.siteName }}</h1>
          <p class="max-w-xl truncate text-sm text-slate-500" :title="data.customerName">{{ data.customerName }}</p>
        </div>
        <div v-if="hasEntries" class="flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
          <span class="text-slate-500">Highest active risk</span>
          <RagBadge :risk="highestActiveRisk" />
        </div>
      </div>

      <!-- No entries state -->
      <div v-if="!hasEntries && !(data.documents ?? []).length" class="jl-card px-6 py-12 text-center text-sm text-slate-400">
        No asbestos risk recorded for this site.
      </div>

      <template v-else>
        <!-- Site Documents -->
        <section class="jl-card mb-6 p-5">
          <h2 class="mb-4 text-lg font-bold text-jl-navy">Site Documents</h2>
          <div class="divide-y divide-slate-100">
            <div
              v-for="d in data.documents"
              :key="d.id"
              class="flex items-center gap-4 py-3"
            >
              <span class="text-rag-red"><BaseIcon name="file" :size="18" /></span>
              <div class="min-w-0 flex-1">
                <p class="truncate font-semibold text-jl-navy" :title="d.fileName">{{ d.fileName }}</p>
                <p class="text-xs text-slate-400">Uploaded {{ formatDate(d.uploadedAt) }} by {{ d.uploadedByName }}</p>
              </div>
              <!-- AMP: show coloured expiry date -->
              <span
                v-if="d.docType === 'AMP'"
                class="inline-flex items-center gap-1.5 text-sm font-semibold"
                :class="ragTextClass(d.ampExpiryRag ?? 'NONE')"
              >
                <span class="h-2 w-2 rounded-full" :class="ragDotClass(d.ampExpiryRag ?? 'NONE')" />
                {{ formatDate(d.ampExpiryDate) }}
              </span>
              <span v-else class="rounded-md bg-slate-200 px-2.5 py-1 text-xs font-bold text-jl-navy">
                {{ docTypeLabel(d.docType) }}
              </span>
              <div class="flex items-center gap-2 text-slate-600">
                <span v-if="docLoadingId === d.id" class="animate-pulse px-2 text-xs text-slate-400">Loading…</span>
                <template v-else>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="View" @click="onViewDoc(d)">
                    <BaseIcon name="eye" :size="18" :stroke-width="2.2" />
                  </button>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="Download" @click="onDownloadDoc(d)">
                    <BaseIcon name="download" :size="18" :stroke-width="2.2" />
                  </button>
                </template>
              </div>
            </div>
            <p v-if="!data.documents.length" class="py-6 text-center text-sm text-slate-400">No documents uploaded yet.</p>
          </div>
        </section>

        <!-- ACM Entries -->
        <h2 class="mb-3 font-bold text-jl-navy">
          {{ acmTotalCount }} ACM entries ({{ activeCount }} active)
        </h2>
        <AcmEntriesTable
          :entries="data.acmEntries ?? []"
          variant="readonly"
          :loading-attachment-id="attLoadingId"
          @view-attachment="onViewAtt"
          @download-attachment="onDownloadAtt"
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
</template>
