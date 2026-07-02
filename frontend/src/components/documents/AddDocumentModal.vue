<script setup lang="ts">
import { ref, computed } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import DocumentUploadList, { type StagedDoc } from '@/components/documents/DocumentUploadList.vue'
import { uploadDocuments } from '@/services/documents.service'
import { toIsoDate } from '@/utils/format'
import { notify } from '@/utils/notify'

const props = defineProps<{ asbestosSiteId: string; siteName: string }>()
const emit = defineEmits<{ close: []; uploaded: [] }>()

const docs = ref<StagedDoc[]>([])
const saving = ref(false)

const ampMissingExpiry = computed(() => docs.value.some((d) => d.docType === 'AMP' && !d.ampExpiryDate))
const canSave = computed(() => docs.value.length > 0 && !ampMissingExpiry.value && !saving.value)

async function save() {
  if (ampMissingExpiry.value) {
    notify.error('AMP Expiry Date is required for AMP documents.')
    return
  }
  saving.value = true
  try {
    // Single multipart request for all files (backend accepts files[] + metadata array).
    await uploadDocuments(props.asbestosSiteId, docs.value.map((d) => ({
      fileName: d.fileName,
      docType: d.docType,
      ampExpiryDate: d.docType === 'AMP' ? toIsoDate(d.ampExpiryDate) : null,
      file: d.file,
    })))
    notify.success('Document(s) uploaded.')
    emit('uploaded')
  } catch (e: any) {
    const msg = e?.response?.data?.detail ?? e?.message ?? 'Upload failed. Please try again.'
    notify.error(msg)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BaseModal eyebrow="Site Documents" title="Add Document" :subtitle="siteName" wide @close="emit('close')">
    <p class="mb-3 text-xs text-slate-400">Upload site-level asbestos documents. Supported formats: PDF, JPEG, PNG.</p>
    <DocumentUploadList v-model="docs" />
    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">Cancel</BaseButton>
      <BaseButton :disabled="!canSave" :loading="saving" @click="save">Save</BaseButton>
    </template>
  </BaseModal>
</template>
