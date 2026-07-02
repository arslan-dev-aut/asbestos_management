<script setup lang="ts">
import { ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { viewFile, downloadFile } from '@/utils/fileStore'
import { resolveAcmAttachmentUrl } from '@/services/register.service'
import { notify } from '@/utils/notify'
import type { AcmAttachment } from '@/types'

defineProps<{
  existing: AcmAttachment[]
  staged: { fileName: string; file: File }[]
  readonly: boolean
  asbestosSiteId?: string  // needed for real-API download; omit in mock
  acmEntryId?: string
}>()
const emit = defineEmits<{ removeExisting: [id: string]; removeStaged: [index: number] }>()

// Separate loading trackers so view + download on the same attachment don't
// overwrite each other's loading state.
const viewingId = ref<string | null>(null)
const downloadingId = ref<string | null>(null)

async function view(att: AcmAttachment, siteId?: string, entryId?: string) {
  if (siteId && entryId) {
    viewingId.value = att.id
    try {
      const url = att.downloadUrl ?? await resolveAcmAttachmentUrl(siteId, entryId, att.id)
      window.open(url, '_blank')
    } catch {
      notify.error('Could not load attachment. Please try again.')
    } finally {
      viewingId.value = null
    }
  } else {
    viewFile(att.fileName, att.fileKey)
  }
}

async function download(att: AcmAttachment, siteId?: string, entryId?: string) {
  if (siteId && entryId) {
    downloadingId.value = att.id
    try {
      const presignedUrl = att.downloadUrl ?? await resolveAcmAttachmentUrl(siteId, entryId, att.id)
      const proxy = `/blob-download?url=${encodeURIComponent(presignedUrl)}&name=${encodeURIComponent(att.fileName)}`
      // Await the proxied fetch so the loading indicator reflects the real
      // download duration, not just the click.
      const resp = await fetch(proxy)
      if (!resp.ok) throw new Error(`Download failed (${resp.status})`)
      const blob = await resp.blob()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = att.fileName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(objectUrl)
    } catch {
      notify.error('Could not download attachment. Please try again.')
    } finally {
      downloadingId.value = null
    }
  } else {
    downloadFile(att.fileName, att.fileKey)
  }
}
</script>

<template>
  <div v-if="existing.length || staged.length" class="mt-3 space-y-2">
    <!-- Existing (saved) attachments -->
    <div
      v-for="att in existing"
      :key="att.id"
      class="flex items-center gap-3 rounded-md border border-slate-200 px-3 py-2"
    >
      <span class="text-jl-teal"><BaseIcon name="paperclip" :size="16" /></span>
      <span class="flex-1 truncate text-sm text-jl-navy">{{ att.fileName }}</span>
      <template v-if="readonly">
        <span v-if="viewingId === att.id" class="text-xs text-slate-400 animate-pulse">Opening…</span>
        <button v-else class="rounded p-1 text-slate-600 transition-colors hover:text-jl-teal" title="View" @click="view(att, asbestosSiteId, acmEntryId)"><BaseIcon name="eye" :size="18" :stroke-width="2.2" /></button>
        <span v-if="downloadingId === att.id" class="text-xs text-slate-400 animate-pulse">Loading…</span>
        <button v-else class="rounded p-1 text-slate-600 transition-colors hover:text-jl-teal" title="Download" @click="download(att, asbestosSiteId, acmEntryId)"><BaseIcon name="download" :size="18" :stroke-width="2.2" /></button>
      </template>
      <button v-else class="rounded p-1 text-slate-600 transition-colors hover:text-rag-red" title="Remove" @click="emit('removeExisting', att.id)"><BaseIcon name="trash" :size="18" :stroke-width="2.2" /></button>
    </div>

    <!-- Newly staged files (add/edit only) -->
    <div
      v-for="(s, i) in staged"
      :key="`staged-${i}`"
      class="flex items-center gap-3 rounded-md border border-jl-teal/40 bg-jl-teal/5 px-3 py-2"
    >
      <span class="text-jl-teal"><BaseIcon name="paperclip" :size="16" /></span>
      <span class="flex-1 truncate text-sm text-jl-navy">{{ s.fileName }}</span>
      <span class="rounded bg-jl-teal/15 px-2 py-0.5 text-xs font-semibold text-jl-teal-dark">New</span>
      <button class="rounded p-1 text-slate-600 transition-colors hover:text-rag-red" title="Remove" @click="emit('removeStaged', i)"><BaseIcon name="trash" :size="18" :stroke-width="2.2" /></button>
    </div>
  </div>
</template>
