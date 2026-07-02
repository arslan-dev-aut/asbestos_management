<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import DocumentUploadList, { type StagedDoc } from '@/components/documents/DocumentUploadList.vue'
import * as svc from '@/services/register.service'
import { uploadDocuments } from '@/services/documents.service'
import { toIsoDate } from '@/utils/format'
import { notify } from '@/utils/notify'
import type { LookupOption } from '@/types'

const emit = defineEmits<{ close: []; created: [asbestosSiteId: string] }>()

const customers = ref<LookupOption[]>([])
const sites = ref<LookupOption[]>([])
const customerId = ref<string | null>(null)
const siteId = ref<string | null>(null)
const docs = ref<StagedDoc[]>([])
const duplicateError = ref('')
const saving = ref(false)
const checkingDuplicate = ref(false)
const searchingCustomers = ref(false)
const searchingSites = ref(false)

// Preload first 50 customers so the dropdown is useful without typing.
svc.getCustomers().then((c) => (customers.value = c)).catch(() => notify.error('Failed to load customers.'))

async function onCustomerSearch(term: string) {
  if (!term) {
    // Search cleared. If a customer is already selected keep it in the list so
    // the label doesn't disappear while we reload the default 50.
    const selected = customers.value.find((c) => c.id === customerId.value) ?? null
    searchingCustomers.value = true
    const fresh = await svc.getCustomers()
    // Merge selected back in if it's not already in the default 50.
    if (selected && !fresh.find((c) => c.id === selected.id)) fresh.unshift(selected)
    customers.value = fresh
    searchingCustomers.value = false
    return
  }
  searchingCustomers.value = true
  const results = await svc.getCustomers(term)
  // Keep the already-selected customer visible even if it's not in the results.
  const selected = customers.value.find((c) => c.id === customerId.value) ?? null
  if (selected && !results.find((c) => c.id === selected.id)) results.unshift(selected)
  customers.value = results
  searchingCustomers.value = false
}

watch(customerId, async (id) => {
  siteId.value = null
  duplicateError.value = ''
  if (!id) { sites.value = []; return }
  searchingSites.value = true
  try {
    sites.value = await svc.getSitesByCustomer(id)
  } finally {
    searchingSites.value = false
  }
})

// As soon as a site is selected, check whether it's already in the register.
watch(siteId, async (id) => {
  duplicateError.value = ''
  if (!id) return
  checkingDuplicate.value = true
  try {
    const existing = await svc.checkSiteExists(id)
    if (existing) duplicateError.value = 'This site is already in the asbestos register.'
  } catch {
    // Silent — if the check fails we fall through to the server-side 409 on save.
  } finally {
    checkingDuplicate.value = false
  }
})

// AMP docs must have an expiry date
const ampMissingExpiry = computed(() => docs.value.some((d) => d.docType === 'AMP' && !d.ampExpiryDate))
const canSave = computed(() => !!customerId.value && !!siteId.value && !ampMissingExpiry.value && !saving.value && !checkingDuplicate.value && !duplicateError.value)

async function save() {
  if (!customerId.value || !siteId.value) return
  if (ampMissingExpiry.value) {
    notify.error('AMP Expiry Date is required for AMP documents.')
    return
  }
  saving.value = true
  duplicateError.value = ''
  try {
    const { asbestosSiteId } = await svc.addSite(customerId.value, siteId.value)
    if (docs.value.length) {
      await uploadDocuments(asbestosSiteId, docs.value.map((d) => ({
        fileName: d.fileName,
        docType: d.docType,
        ampExpiryDate: d.docType === 'AMP' ? toIsoDate(d.ampExpiryDate) : null,
        file: d.file,
      })))
    }
    notify.success('Site added to the asbestos register.')
    emit('created', asbestosSiteId)
  } catch (e: any) {
    // If the site already exists (409 — e.g. prior request timed out but succeeded),
    // navigate straight to it rather than blocking the user with an error.
    if (e?.asbestosSiteId) {
      notify.warning('This site was already added. Taking you there now.')
      emit('created', e.asbestosSiteId)
      return
    }
    duplicateError.value = e?.message ?? 'Something went wrong. Please try again.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BaseModal eyebrow="Asbestos Register" title="Add New Site" wide @close="emit('close')">
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="jl-label">Customer <span class="text-rag-red">*</span></label>
        <BaseSelect v-model="customerId" :options="customers.map((c) => ({ value: c.id, label: c.name }))" placeholder="Select customer" server-search :searching="searchingCustomers" @search="onCustomerSearch" />
      </div>
      <div>
        <label class="jl-label">Site <span class="text-rag-red">*</span></label>
        <BaseSelect v-model="siteId" :options="sites.map((s) => ({ value: s.id, label: s.name }))" placeholder="Select site" :disabled="!customerId" :searching="searchingSites" />
      </div>
    </div>

    <div v-if="checkingDuplicate" class="mt-3 flex items-center gap-2 px-1 text-sm text-slate-400 animate-pulse">
      Checking register…
    </div>
    <div v-else-if="duplicateError" class="mt-3 flex items-center gap-2 rounded-md border border-rag-red/30 bg-rag-red-bg px-3 py-2 text-sm font-semibold text-rag-red">
      ⚠ {{ duplicateError }}
    </div>

    <div class="mt-5">
      <h3 class="jl-label">Site Documents</h3>
      <p class="mb-2 text-xs text-slate-400">Upload site-level asbestos documents. Supported formats: PDF, JPEG, PNG.</p>
      <DocumentUploadList v-model="docs" />
      <p class="mt-3 flex items-center gap-2 text-xs text-slate-500">
        🛡 Recommended: Upload the site’s AMP and latest survey report.
      </p>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">Cancel</BaseButton>
      <BaseButton :disabled="!canSave" :loading="saving" @click="save">Save</BaseButton>
    </template>
  </BaseModal>
</template>
