<script setup lang="ts">
import AcmEntriesTable from '@/components/register/AcmEntriesTable.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { viewFile, downloadFile } from '@/utils/fileStore'
import { docTypeLabel } from '@/utils/const'
import { formatDate } from '@/utils/format'
import { ragDotClass, ragTextClass } from '@/utils/rag'
import type { ReadonlySiteData } from '@/types'

// Shared read-only site view used by the QR public page and the View-Only
// portal tabs. Documents at top (no superseded AMPs), ACM table below.
// hideAsset is set by the QR page (Asset column hidden there).
const props = withDefaults(defineProps<{ data: ReadonlySiteData; hideAsset?: boolean }>(), {
  hideAsset: false,
})

const hasEntries = () => props.data.acmEntries.length > 0

function viewDoc(name: string, key?: string | null) {
  viewFile(name, key)
}
function downloadDoc(name: string, key?: string | null) {
  downloadFile(name, key)
}
</script>

<template>
  <div v-if="!hasEntries()" class="jl-card p-8 text-center text-slate-500">
    No asbestos risk recorded for this site.
  </div>

  <template v-else>
    <!-- Site documents (latest AMP only with expiry RAG, survey, air monitoring) -->
    <section class="jl-card mb-6 p-5">
      <h2 class="mb-3 text-lg font-bold text-jl-navy">Site Documents</h2>
      <div class="divide-y divide-slate-100">
        <div v-for="d in data.documents" :key="d.id" class="flex items-center gap-4 py-3">
          <span class="text-rag-red"><BaseIcon name="file" :size="18" /></span>
          <div class="flex-1">
            <p class="font-semibold text-jl-navy">{{ d.fileName }}</p>
            <p class="text-xs text-slate-400">Uploaded {{ formatDate(d.uploadedAt) }}</p>
          </div>
          <span class="rounded-md bg-slate-200 px-2.5 py-1 text-xs font-bold text-jl-navy">{{ docTypeLabel(d.docType) }}</span>
          <span v-if="d.docType === 'AMP'" class="inline-flex items-center gap-1.5 text-sm font-semibold" :class="ragTextClass(d.ampExpiryRag ?? 'NONE')">
            <span class="h-2 w-2 rounded-full" :class="ragDotClass(d.ampExpiryRag ?? 'NONE')" />
            {{ formatDate(d.ampExpiryDate) }}
          </span>
          <div class="flex items-center gap-2 text-slate-600">
            <button class="rounded p-1 transition-colors hover:text-jl-teal" title="View" @click="viewDoc(d.fileName, d.fileKey)"><BaseIcon name="eye" :size="18" :stroke-width="2.2" /></button>
            <button class="rounded p-1 transition-colors hover:text-jl-teal" title="Download" @click="downloadDoc(d.fileName, d.fileKey)"><BaseIcon name="download" :size="18" :stroke-width="2.2" /></button>
          </div>
        </div>
        <p v-if="!data.documents.length" class="py-4 text-center text-sm text-slate-400">No documents available.</p>
      </div>
    </section>

    <!-- Read-only ACM entries (shared table) -->
    <h2 class="mb-3 font-bold text-jl-navy">{{ data.acmEntries.length }} ACM entries</h2>
    <AcmEntriesTable
      :entries="data.acmEntries"
      variant="readonly"
      :hide-asset="hideAsset"
      @view-attachment="viewDoc"
      @download-attachment="downloadDoc"
    />
  </template>
</template>
