<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { getQrCode } from '@/services/qrcode.service'
import { notify } from '@/utils/notify'

const props = defineProps<{ asbestosSiteId: string; siteName: string }>()
const emit = defineEmits<{ close: [] }>()

const previewUrl = ref('')
const qrDataUrl = ref('')
const downloading = ref(false)

// The backend returns previewUrl as something like
// "localhost:9/public/{token}" (or an ngrok host). The token is the last path
// segment. We render the view-only page inside THIS app at
// /site/{token}/asbestos, so rebuild the link against the current origin while
// preserving the token. (The raw /public/{token} link still works directly
// against the backend; this just keeps Preview within the running frontend.)
function toAppPreviewUrl(backendUrl: string): string {
  try {
    const token = backendUrl.split('/').filter(Boolean).pop() ?? ''
    return `${window.location.origin}/site/${token}/asbestos`
  } catch {
    return backendUrl
  }
}

onMounted(async () => {
  try {
    const qr = await getQrCode(props.asbestosSiteId)
    previewUrl.value = toAppPreviewUrl(qr.previewUrl)
    // Use the backend-rendered QR image directly. No client-side fallback —
    // if the API didn't return an image, that's an error we want to surface.
    if (!qr.qrImageUrl) throw new Error('No QR image returned by the server.')
    qrDataUrl.value = qr.qrImageUrl
  } catch {
    notify.error('Could not load the QR code for this site.')
  }
})

function copyUrl() {
  navigator.clipboard?.writeText(previewUrl.value)
  notify.success('Link copied.')
}
async function download() {
  if (!qrDataUrl.value || downloading.value) return
  // The QR image is a cross-origin Azure blob URL — browsers ignore the
  // `download` attribute cross-origin and just open it. Route through the
  // local /blob-download proxy (same as document downloads) so Node fetches
  // it server-side with Content-Disposition: attachment, forcing a save.
  const fileName = `${props.siteName} - QR.png`
  const proxy = `/blob-download?url=${encodeURIComponent(qrDataUrl.value)}&name=${encodeURIComponent(fileName)}`
  downloading.value = true
  try {
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
  } catch {
    notify.error('Could not download the QR code.')
  } finally {
    downloading.value = false
  }
}
function print() {
  const w = window.open('', '_blank')
  if (w) {
    w.document.write(`<img src="${qrDataUrl.value}" style="width:300px" onload="window.print();window.close()" />`)
    w.document.close()
  }
}
function preview() {
  window.open(previewUrl.value, '_blank')
}
</script>

<template>
  <BaseModal eyebrow="Site Access" :title="`QR Code — ${siteName}`" @close="emit('close')">
    <div class="flex flex-col items-center">
      <div class="rounded-xl bg-white p-4 shadow">
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="Site QR code" class="h-56 w-56" />
        <div v-else class="flex h-56 w-56 items-center justify-center text-slate-300">Generating…</div>
      </div>
      <p class="mt-4 text-center text-sm text-slate-500">
        Scan this QR code to view the asbestos register for this site.<br />
        No JobLogic login required — read-only access.
      </p>
      <div class="mt-3 flex w-full items-center gap-2">
        <input :value="previewUrl" readonly class="jl-input text-xs" />
        <button class="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50" @click="copyUrl">⧉</button>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="preview"><BaseIcon name="external" :size="15" /> Preview what visitors will see</BaseButton>
      <BaseButton variant="secondary" @click="print">🖨 Print</BaseButton>
      <BaseButton variant="dark" :loading="downloading" @click="download"><BaseIcon v-if="!downloading" name="download" :size="15" /> Download QR Code</BaseButton>
    </template>
  </BaseModal>
</template>
