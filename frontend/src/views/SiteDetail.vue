<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import RagBadge from '@/components/base/RagBadge.vue'
import Pagination from '@/components/base/Pagination.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import AcmEntryModal from '@/components/register/AcmEntryModal.vue'
import AcmEntriesTable from '@/components/register/AcmEntriesTable.vue'
import AddDocumentModal from '@/components/documents/AddDocumentModal.vue'
import QrCodeModal from '@/components/register/QrCodeModal.vue'
import AuditTrailTab from '@/components/register/AuditTrailTab.vue'
import * as reg from '@/services/register.service'
import { getDocumentsPaged, viewDocument, downloadDocument, removeDocument } from '@/services/documents.service'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass, highestRisk } from '@/utils/rag'
import { docTypeLabel, PAGE_SIZE } from '@/utils/const'
import { notify } from '@/utils/notify'
import type { SiteDetail, AcmEntry, SiteDocument } from '@/types'

const props = defineProps<{ asbestosSiteId: string }>()
const router = useRouter()

const tab = ref<'acm' | 'audit'>('acm')
const site = ref<SiteDetail | null>(null)
const documents = ref<SiteDocument[]>([])       // current visible page
const allDocuments = ref<SiteDocument[]>([])     // full set (for AMP banner)
const entries = ref<AcmEntry[]>([])
const acmTotalCount = ref(0)
const loading = ref(true)

// Server-side ACM pagination
const pageIndex = ref(0)

// Server-side Site Documents pagination
const DOC_PAGE_SIZE = 10
const docPageIndex = ref(0)
const docTotalCount = ref(0)

// Modals
const modalMode = ref<'add' | 'edit' | 'view' | null>(null)
const activeEntry = ref<AcmEntry | null>(null)
const showAddDoc = ref(false)
const showQr = ref(false)
const pendingRemediate = ref<AcmEntry | null>(null)
const pendingRemoveDoc = ref<SiteDocument | null>(null)
const docLoadingId = ref<string | null>(null)
const togglingId = ref<string | null>(null)
const docsLoading = ref(false)
const entriesLoading = ref(false)
const removingDocId = ref<string | null>(null)

const highestActiveRisk = computed(() =>
  highestRisk(entries.value.filter((e) => e.status === 'ACTIVE').map((e) => e.riskScore)),
)
const activeCount = computed(() => entries.value.filter((e) => e.status === 'ACTIVE').length)
// Current AMP for the banner — sourced from the full doc set (not the paged
// list), since the current AMP may not be on the visible documents page.
const currentAmp = computed(() => allDocuments.value.find((d) => d.docType === 'AMP' && d.isCurrentAmp) ?? null)
const currentAmpExpired = computed(() => currentAmp.value?.ampExpiryRag === 'RED')
const currentAmpExpiringSoon = computed(() => currentAmp.value?.ampExpiryRag === 'AMBER')
const expiredAmpDate = computed(() => currentAmp.value?.ampExpiryDate ?? null)

async function load() {
  loading.value = true
  try {
    const full = await reg.getSiteFull(props.asbestosSiteId)
    site.value = full.site
    allDocuments.value = full.documents
    entries.value = full.acmEntries
    acmTotalCount.value = full.acmTotalCount
    // First page of documents (newest-first, server-side paginated).
    await loadDocPage(0)
    if (entries.value.some((e) => e.assetDiscrepancy)) {
      notify.warning('One or more ACM entries reference an asset that no longer exists. Please review.')
    }
  } catch {
    notify.error('Failed to load site.')
  } finally {
    loading.value = false
  }
}

let acmSeq = 0
async function loadAcmPage(page: number) {
  const seq = ++acmSeq
  entriesLoading.value = true
  pageIndex.value = page
  try {
    const result = await reg.getAcmEntriesPaged(props.asbestosSiteId, { page, pageSize: PAGE_SIZE, statusFilter: 'all' })
    if (seq !== acmSeq) return
    entries.value = result.items
    acmTotalCount.value = result.totalCount
  } catch {
    if (seq !== acmSeq) return
    notify.error('Failed to load ACM entries.')
  } finally {
    if (seq === acmSeq) entriesLoading.value = false
  }
}

onMounted(load)

function openAdd() { activeEntry.value = null; modalMode.value = 'add' }
function openEdit(e: AcmEntry) { activeEntry.value = e; modalMode.value = 'edit' }
function openView(e: AcmEntry) { activeEntry.value = e; modalMode.value = 'view' }
function closeModal() { modalMode.value = null; activeEntry.value = null }

async function onSaved() {
  await loadAcmPage(pageIndex.value)
}

function askRemediate(e: AcmEntry) {
  if (e.status === 'ACTIVE') pendingRemediate.value = e
  else doToggle(e, 'ACTIVE')
}
async function doToggle(e: AcmEntry, status: AcmEntry['status']) {
  togglingId.value = e.id
  pendingRemediate.value = null
  try {
    await reg.toggleAcmStatus(props.asbestosSiteId, e.id, status)
    notify.success(status === 'REMEDIATED' ? 'Entry marked as Remediated.' : 'Entry reactivated.')
    await loadAcmPage(pageIndex.value)
  } catch {
    notify.error('Could not update entry status.')
  } finally {
    togglingId.value = null
  }
}

async function onViewDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await viewDocument(props.asbestosSiteId, d) }
  finally { docLoadingId.value = null }
}
async function onDownloadDoc(d: SiteDocument) {
  docLoadingId.value = d.id
  try { await downloadDocument(props.asbestosSiteId, d) }
  finally { docLoadingId.value = null }
}
let docSeq = 0
async function loadDocPage(page: number) {
  const seq = ++docSeq
  docsLoading.value = true
  docPageIndex.value = page
  try {
    const res = await getDocumentsPaged(props.asbestosSiteId, { page, pageSize: DOC_PAGE_SIZE })
    if (seq !== docSeq) return
    documents.value = res.items
    docTotalCount.value = res.totalCount
  } catch {
    if (seq !== docSeq) return
    notify.error('Failed to load documents.')
  } finally {
    if (seq === docSeq) docsLoading.value = false
  }
}
async function reloadDocuments() {
  // Refresh the full set (for the AMP banner) and the current page.
  const full = await reg.getSiteFull(props.asbestosSiteId)
  allDocuments.value = full.documents
  await loadDocPage(0)
}
async function onDocUploaded() {
  showAddDoc.value = false
  await reloadDocuments()
}
async function confirmRemoveDoc() {
  if (!pendingRemoveDoc.value) return
  const id = pendingRemoveDoc.value.id
  removingDocId.value = id
  pendingRemoveDoc.value = null
  try {
    await removeDocument(props.asbestosSiteId, id)
    notify.success('Document removed.')
    await reloadDocuments()
  } finally {
    removingDocId.value = null
  }
}
</script>

<template>
  <div>
    <!-- Breadcrumb — always visible immediately -->
    <nav class="mb-1 text-sm text-jl-teal">
      <span class="cursor-pointer" @click="router.push('/asbestos-register')">Settings</span> /
      <span class="cursor-pointer" @click="router.push('/asbestos-register')">Library</span> /
      <span class="cursor-pointer" @click="router.push('/asbestos-register')">Asbestos Register</span> /
      <span v-if="loading" class="inline-block h-3 w-24 animate-pulse rounded bg-slate-200 align-middle" />
      <span v-else class="inline-block max-w-xs truncate align-bottom text-jl-navy" :title="site?.siteName">{{ site?.siteName }}</span>
    </nav>

    <!-- Page header — skeleton while loading -->
    <div class="mb-4 flex items-start justify-between">
      <div>
        <template v-if="loading">
          <div class="mb-2 h-7 w-56 animate-pulse rounded bg-slate-200" />
          <div class="h-4 w-36 animate-pulse rounded bg-slate-100" />
        </template>
        <template v-else>
          <h1 class="max-w-xl truncate text-2xl font-bold text-jl-navy" :title="site?.siteName">{{ site?.siteName }}</h1>
          <p class="max-w-xl truncate text-sm text-slate-500" :title="site?.customerName">{{ site?.customerName }}</p>
        </template>
      </div>
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
          <span class="text-slate-500">Highest active risk</span>
          <span v-if="loading" class="h-5 w-12 animate-pulse rounded bg-slate-200" />
          <RagBadge v-else :risk="highestActiveRisk" />
        </div>
      </div>
    </div>

    <!-- Tabs — always visible -->
    <div class="mb-5 flex gap-6 border-b border-slate-200 text-sm font-semibold">
      <button class="-mb-px border-b-2 pb-3" :class="tab === 'acm' ? 'border-jl-teal text-jl-navy' : 'border-transparent text-slate-400'" @click="tab = 'acm'">ACM Entries</button>
      <button class="-mb-px border-b-2 pb-3" :class="tab === 'audit' ? 'border-jl-teal text-jl-navy' : 'border-transparent text-slate-400'" @click="tab = 'audit'">Audit Trail</button>
    </div>

    <template v-if="tab === 'acm'">
      <!-- AMP banners -->
      <div v-if="!loading && currentAmpExpired" class="mb-4 flex items-center gap-2.5 rounded-lg border border-rag-red/30 bg-rag-red-bg px-4 py-3 text-sm text-rag-red">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M10.3 3.2 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.2a2 2 0 0 0-3.4 0Z" />
          <path d="M12 9v4" /><path d="M12 17h.01" />
        </svg>
        <span><span class="font-bold">AMP expired</span> <span class="font-normal opacity-80">— last AMP expired on {{ formatDate(expiredAmpDate) }}. Please upload a renewed AMP.</span></span>
      </div>
      <div v-else-if="!loading && currentAmpExpiringSoon" class="mb-4 flex items-center gap-2.5 rounded-lg border border-rag-warn/30 bg-rag-warn-bg px-4 py-3 text-sm text-rag-warn">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M10.3 3.2 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.2a2 2 0 0 0-3.4 0Z" />
          <path d="M12 9v4" /><path d="M12 17h.01" />
        </svg>
        <span><span class="font-bold">AMP expiring soon</span> <span class="font-normal opacity-80">— expires on {{ formatDate(expiredAmpDate) }}.</span></span>
      </div>

      <!-- Site Documents -->
      <section class="jl-card mb-6 p-5">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-bold text-jl-navy">Site Documents</h2>
          <div class="flex gap-2">
            <BaseButton variant="secondary" size="sm" :disabled="loading" @click="showQr = true"><BaseIcon name="qr" :size="15" /> Generate QR Code</BaseButton>
            <BaseButton variant="secondary" size="sm" :disabled="loading" @click="showAddDoc = true"><BaseIcon name="plus" :size="15" /> Add Document</BaseButton>
          </div>
        </div>

        <!-- Skeleton rows while loading -->
        <template v-if="loading || docsLoading">
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
              <div class="h-7 w-7 animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        </template>
        <div v-else class="divide-y divide-slate-100">
          <div v-for="d in documents" :key="d.id" class="flex items-center gap-4 py-3" :class="{ 'opacity-50': (d.docType === 'AMP' && !d.isCurrentAmp) || removingDocId === d.id }">
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
              <span v-if="removingDocId === d.id" class="px-1 text-xs animate-pulse text-slate-400">Removing…</span>
              <button v-else class="rounded p-1 transition-colors hover:text-rag-red" title="Remove" @click="pendingRemoveDoc = d"><BaseIcon name="trash" :size="18" :stroke-width="2.2" /></button>
            </div>
          </div>
          <p v-if="!documents.length" class="py-6 text-center text-sm text-slate-400">No documents uploaded yet.</p>
        </div>
        <Pagination
          v-if="!loading"
          :page-index="docPageIndex"
          :page-size="DOC_PAGE_SIZE"
          :total-count="docTotalCount"
          @update:page-index="loadDocPage($event)"
        />
      </section>

      <!-- ACM Entries header -->
      <div class="mb-3 flex items-center justify-between">
        <div v-if="loading || entriesLoading" class="h-5 w-44 animate-pulse rounded bg-slate-200" />
        <h2 v-else class="font-bold text-jl-navy">{{ acmTotalCount }} ACM entries ({{ activeCount }} active)</h2>
        <BaseButton @click="openAdd">+ Add ACM Entry</BaseButton>
      </div>

      <!-- ACM Entries skeleton -->
      <template v-if="loading || entriesLoading">
        <div class="jl-card overflow-hidden">
          <div v-for="n in 4" :key="n" class="flex items-center gap-6 border-b border-slate-100 px-4 py-3 last:border-0">
            <div class="h-4 w-28 animate-pulse rounded bg-slate-200" />
            <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
            <div class="h-4 w-20 animate-pulse rounded bg-slate-200" />
            <div class="h-4 w-24 animate-pulse rounded bg-slate-200" />
            <div class="h-5 w-14 animate-pulse rounded bg-slate-100" />
            <div class="ml-auto flex gap-2">
              <div class="h-7 w-12 animate-pulse rounded bg-slate-100" />
              <div class="h-7 w-12 animate-pulse rounded bg-slate-100" />
              <div class="h-7 w-24 animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <AcmEntriesTable
          :entries="entries"
          variant="admin"
          :toggling-id="togglingId"
          @view="openView"
          @edit="openEdit"
          @toggle-status="askRemediate"
        />
        <Pagination :page-index="pageIndex" :page-size="PAGE_SIZE" :total-count="acmTotalCount" @update:page-index="loadAcmPage($event)" />
      </template>
    </template>

    <!-- Audit trail -->
    <AuditTrailTab v-else :asbestos-site-id="asbestosSiteId" />

    <!-- Modals — guard on site being loaded -->
    <AcmEntryModal
      v-if="modalMode && site"
      :mode="modalMode"
      :asbestos-site-id="asbestosSiteId"
      :site-id="site.siteId"
      :site-name="site.siteName"
      :entry="activeEntry"
      @close="closeModal"
      @saved="onSaved"
      @status-changed="onSaved"
    />
    <AddDocumentModal
      v-if="showAddDoc && site"
      :asbestos-site-id="asbestosSiteId"
      :site-name="site.siteName"
      @close="showAddDoc = false"
      @uploaded="onDocUploaded"
    />
    <QrCodeModal v-if="showQr && site" :asbestos-site-id="asbestosSiteId" :site-name="site.siteName" @close="showQr = false" />

    <ConfirmDialog
      v-if="pendingRemediate"
      title="Mark this entry as Remediated?"
      message="This entry will no longer appear on mobile acknowledgement screens for engineers visiting this site. The record will be preserved for audit purposes."
      @confirm="doToggle(pendingRemediate, 'REMEDIATED')"
      @cancel="pendingRemediate = null"
    />
    <ConfirmDialog
      v-if="pendingRemoveDoc"
      title="Remove this document?"
      :message="`'${pendingRemoveDoc.fileName}' will be removed from this site. This action is logged in the audit trail.`"
      confirm-label="Remove"
      @confirm="confirmRemoveDoc"
      @cancel="pendingRemoveDoc = null"
    />
  </div>
</template>
