<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import RagBadge from '@/components/base/RagBadge.vue'
import AcmEntriesTable from '@/components/register/AcmEntriesTable.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { getPublicSite } from '@/services/qrcode.service'
import { docTypeLabel } from '@/utils/const'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass, highestRisk } from '@/utils/rag'
import type { ReadonlySiteData, SiteDocument, AcmAttachment } from '@/types'

const props = defineProps<{ token: string }>()

const data = ref<ReadonlySiteData | null>(null)
const error = ref('')
const loading = ref(true)
// Track in-flight view/download per file so the row shows a spinner.
const busyKey = ref<string | null>(null)

// Active ACM entries only — the public page is for on-site visitors.
const activeEntries = computed(() => (data.value?.acmEntries ?? []).filter((e) => e.status === 'ACTIVE'))
const highestActiveRisk = computed(() => highestRisk(activeEntries.value.map((e) => e.riskScore)))

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getPublicSite(props.token)
  } catch (e) {
    error.value = (e as Error).message || 'This link is invalid or has expired.'
  } finally {
    loading.value = false
  }
})

// Open a presigned URL in a new tab.
function openUrl(url: string | null | undefined) {
  if (url) window.open(url, '_blank')
}

// Force a save-to-disk via the /blob-download dev proxy (cross-origin blob URLs
// otherwise just open in-tab). Awaits the full fetch so the spinner reflects
// the real download duration.
async function saveUrl(url: string | null | undefined, fileName: string) {
  if (!url) return
  const proxy = `/blob-download?url=${encodeURIComponent(url)}&name=${encodeURIComponent(fileName)}`
  const resp = await fetch(proxy)
  if (!resp.ok) throw new Error(`Download failed (${resp.status})`)
  const blob = await resp.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}

async function onViewDoc(d: SiteDocument) {
  busyKey.value = d.id
  try { openUrl(d.downloadUrl ?? d.fileUrl) }
  finally { busyKey.value = null }
}
async function onDownloadDoc(d: SiteDocument) {
  busyKey.value = d.id
  try { await saveUrl(d.downloadUrl ?? d.fileUrl, d.fileName) }
  catch { /* surfaced via the row reverting; public page has no toast host */ }
  finally { busyKey.value = null }
}

// ACM attachment view/download — resolve the attachment by fileName (the table
// emits the file name) against the mapped presigned URLs.
function findAtt(fileName: string): AcmAttachment | null {
  for (const e of data.value?.acmEntries ?? []) {
    const att = e.attachments.find((a) => a.fileName === fileName)
    if (att) return att
  }
  return null
}
function onViewAtt(fileName: string) {
  const att = findAtt(fileName)
  openUrl(att?.downloadUrl ?? att?.fileUrl)
}
async function onDownloadAtt(fileName: string) {
  const att = findAtt(fileName)
  if (att) await saveUrl(att.downloadUrl ?? att.fileUrl, att.fileName)
}
</script>

<template>
  <div class="min-h-full bg-[#eef1f4]">
    <!-- Public topbar -->
    <header class="flex items-center justify-between bg-jl-navy-dark px-6 py-3 text-white">
      <span class="text-lg font-bold">joblogic</span>
      <span class="inline-flex items-center gap-1.5 text-sm text-slate-200">
        <BaseIcon name="external" :size="15" /> Public Site Access
      </span>
    </header>

    <div class="mx-auto max-w-5xl px-6 py-8">
      <!-- Error -->
      <div v-if="error" class="jl-card p-8 text-center text-rag-red">{{ error }}</div>

      <!-- Loading -->
      <LoadingState v-else-if="loading" message="Loading site information…" />

      <template v-else-if="data">
        <!-- Site header card -->
        <div class="jl-card mb-6 flex items-start justify-between p-6">
          <div>
            <h1 class="text-2xl font-bold text-jl-navy">{{ data.siteName }}</h1>
            <p class="mt-1 text-sm text-slate-500">{{ data.customerName }}</p>
          </div>
          <div v-if="activeEntries.length" class="flex items-center gap-2 rounded-md bg-white px-3 py-2 text-sm shadow-sm">
            <span class="text-slate-500">Highest active risk</span>
            <RagBadge :risk="highestActiveRisk" />
          </div>
        </div>

        <!-- Site Documents -->
        <h2 class="mb-3 flex items-center gap-2 text-lg font-bold text-jl-navy">
          <BaseIcon name="file" :size="18" /> Site Documents
        </h2>
        <section class="jl-card mb-8 p-2">
          <div class="divide-y divide-slate-100">
            <div v-for="d in data.documents" :key="d.id" class="flex items-center gap-4 px-4 py-3">
              <span class="text-rag-red"><BaseIcon name="file" :size="18" /></span>
              <div class="flex-1 min-w-0">
                <p class="truncate font-semibold text-jl-navy" :title="d.fileName">{{ d.fileName }}</p>
              </div>
              <!-- AMP rows show the coloured expiry date; others show a type chip -->
              <span
                v-if="d.docType === 'AMP'"
                class="inline-flex items-center gap-1.5 text-sm font-semibold"
                :class="ragTextClass(d.ampExpiryRag ?? 'NONE')"
              >
                <span class="h-2 w-2 rounded-full" :class="ragDotClass(d.ampExpiryRag ?? 'NONE')" />
                {{ formatDate(d.ampExpiryDate) }}
              </span>
              <span v-else class="rounded-md bg-slate-200 px-2.5 py-1 text-xs font-bold text-jl-navy">{{ docTypeLabel(d.docType) }}</span>
              <div class="flex items-center gap-2 text-slate-600">
                <span v-if="busyKey === d.id" class="px-2 text-xs animate-pulse text-slate-400">Loading…</span>
                <template v-else>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="View" @click="onViewDoc(d)"><BaseIcon name="eye" :size="18" :stroke-width="2.2" /></button>
                  <button class="rounded p-1 transition-colors hover:text-jl-teal" title="Download" @click="onDownloadDoc(d)"><BaseIcon name="download" :size="18" :stroke-width="2.2" /></button>
                </template>
              </div>
            </div>
            <p v-if="!data.documents.length" class="py-6 text-center text-sm text-slate-400">No documents available for this site.</p>
          </div>
        </section>

        <!-- Active ACM Entries -->
        <h2 class="mb-3 flex items-center gap-2 text-lg font-bold text-jl-navy">
          <BaseIcon name="file" :size="18" /> Active ACM Entries
          <span class="rounded-full bg-jl-teal px-2.5 py-0.5 text-sm font-bold text-white">{{ activeEntries.length }}</span>
        </h2>
        <AcmEntriesTable
          :entries="activeEntries"
          variant="readonly"
          :hide-asset="true"
          @view-attachment="onViewAtt"
          @download-attachment="onDownloadAtt"
        />

        <p class="mt-8 text-center text-xs text-slate-400">
          This information is provided for on-site reference only. For queries, contact your account manager.<br />
          <span class="text-slate-300">Generated via Joblogic Asbestos Management Module</span>
        </p>
      </template>
    </div>
  </div>
</template>
