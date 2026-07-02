<script setup lang="ts">
import { ref, computed } from 'vue'
import { useColumnResize } from '@/composables/useColumnResize'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import * as svc from '@/services/bulk.service'
import { useBulkJob } from '@/composables/useBulkJob'
import { ACCEPTED_BULK_EXT } from '@/utils/const'
import { notify } from '@/utils/notify'

const emit = defineEmits<{ close: [] }>()

const bulk = useBulkJob()

// Bulk validation table columns
const { colWidths: bulkColWidths, startResize: bulkStartResize } = useColumnResize([50, 80, 160, 160, 160, 200])

const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

// Whether the user chose to stay and watch progress after clicking Validate.
const waitingHere = ref(false)

// Derived step from global job state.
const step = computed(() => {
  if (bulk.state.value === 'idle') return 1
  if (bulk.state.value === 'validating') return waitingHere.value ? 'progress' : 'go-or-stay'
  if (bulk.state.value === 'validated') return 2
  if (bulk.state.value === 'confirming') return 'confirming'
  if (bulk.state.value === 'done') return 4
  if (bulk.state.value === 'error') return 'error'
  return 1
})

const progressBarStyle = computed(() => ({
  width: `${bulk.progress.value}%`,
  transition: 'width 0.15s ease-out',
}))

function pick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f && !/\.(csv|xlsx)$/i.test(f.name)) {
    notify.error('Only CSV or Excel (.xlsx) files are accepted.')
    return
  }
  file.value = f ?? null
}

async function validate() {
  if (!file.value) return
  waitingHere.value = false
  // Start validation in background immediately — modal shows stay/go choice.
  bulk.startValidation(file.value)
}

function keepWorking() {
  // User chose to browse while validation runs — close the modal.
  emit('close')
}

function waitHere() {
  waitingHere.value = true
}

function startOver() {
  bulk.reset()
  file.value = null
  waitingHere.value = false
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <BaseModal eyebrow="Asbestos Register" title="Bulk Upload" subtitle="Import ACM entries across multiple sites" wide @close="emit('close')">

    <!-- Step 1: template + upload -->
    <div v-if="step === 1">
      <div class="rounded-md bg-slate-50 p-4">
        <p class="text-sm font-semibold text-jl-navy">Step 1 — Download the template</p>
        <p class="mb-3 text-xs text-slate-500">Columns: {{ svc.BULK_TEMPLATE_COLUMNS.join(', ') }}</p>
        <BaseButton variant="secondary" size="sm" @click="svc.downloadTemplate()"><BaseIcon name="download" :size="15" /> Download Template</BaseButton>
      </div>
      <div class="mt-4">
        <p class="jl-label">Upload completed file</p>
        <input ref="fileInput" type="file" :accept="ACCEPTED_BULK_EXT" class="hidden" @change="pick" />
        <div class="flex items-center gap-3">
          <BaseButton variant="secondary" @click="fileInput?.click()">Choose file</BaseButton>
          <span class="text-sm text-slate-500">{{ file?.name ?? 'No file selected (CSV or .xlsx)' }}</span>
        </div>
      </div>
    </div>

    <!-- Stay or go choice — shown immediately after clicking Validate -->
    <div v-else-if="step === 'go-or-stay'" class="py-2">
      <p class="mb-4 text-sm font-semibold text-jl-navy">Validation is running for <span class="text-jl-teal">{{ file?.name }}</span></p>
      <!-- Progress bar -->
      <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>Validating…</span>
        <span>{{ Math.round(bulk.progress.value) }}%</span>
      </div>
      <div class="mb-5 h-2 overflow-hidden rounded-full bg-slate-200">
        <div class="h-full rounded-full bg-jl-teal" :style="progressBarStyle" />
      </div>
      <div class="rounded-md border border-slate-200 bg-slate-50 p-4">
        <p class="mb-1 text-sm font-semibold text-jl-navy">What would you like to do while validation runs?</p>
        <p class="mb-4 text-xs text-slate-500">You can close this and continue working. A notification will appear when validation is complete and the status bar at the top will show progress.</p>
        <div class="flex gap-3">
          <BaseButton variant="secondary" @click="keepWorking">Keep working</BaseButton>
          <BaseButton @click="waitHere">Wait here</BaseButton>
        </div>
      </div>
    </div>

    <!-- Waiting here — full progress view -->
    <div v-else-if="step === 'progress'" class="py-4">
      <p class="mb-4 text-sm font-semibold text-jl-navy">Validating <span class="text-jl-teal">{{ file?.name }}</span>…</p>
      <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>Processing rows…</span>
        <span class="font-semibold">{{ Math.round(bulk.progress.value) }}%</span>
      </div>
      <div class="mb-2 h-3 overflow-hidden rounded-full bg-slate-200">
        <div class="h-full rounded-full bg-jl-teal" :style="progressBarStyle" />
      </div>
      <p class="text-xs text-slate-400">This may take a moment depending on file size.</p>
    </div>

    <!-- Step 2: validation results -->
    <div v-else-if="step === 2 && bulk.result.value">
      <div class="mb-3 text-sm font-semibold">
        <span class="text-jl-green-dark">{{ bulk.result.value.validCount }} entries valid</span>,
        <span class="text-rag-red">{{ bulk.result.value.errorCount }} entries with errors</span>
      </div>
      <div class="max-h-72 overflow-auto rounded-md border border-slate-200">
        <table class="text-xs" style="table-layout: fixed; width: 100%; min-width: max-content">
          <colgroup>
            <col v-for="(w, i) in bulkColWidths" :key="i" :style="{ width: w + 'px' }" />
          </colgroup>
          <thead class="bg-slate-50 text-left font-semibold uppercase text-slate-500">
            <tr>
              <th class="relative select-none px-3 py-2">
                #
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="bulkStartResize($event, 0)" />
              </th>
              <th class="relative select-none px-3 py-2">
                Status
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="bulkStartResize($event, 1)" />
              </th>
              <th class="relative select-none px-3 py-2">
                Site
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="bulkStartResize($event, 2)" />
              </th>
              <th class="relative select-none px-3 py-2">
                Building
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="bulkStartResize($event, 3)" />
              </th>
              <th class="relative select-none px-3 py-2">
                ACM Type
                <span class="absolute inset-y-0 right-0 w-1 cursor-col-resize bg-slate-200 opacity-0 hover:opacity-100 active:opacity-100" @mousedown.prevent="bulkStartResize($event, 4)" />
              </th>
              <th class="px-3 py-2">Detail</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="r in bulk.result.value.rows" :key="r.rowIndex">
              <td class="overflow-hidden px-3 py-2">{{ r.rowIndex }}</td>
              <td class="overflow-hidden px-3 py-2">
                <span v-if="r.status === 'VALID'" class="text-jl-green-dark">✓ Valid</span>
                <span v-else class="text-rag-red">✕ Error</span>
              </td>
              <td class="overflow-hidden px-3 py-2">
                <span class="block truncate" :title="r.siteName">{{ r.siteName }}</span>
              </td>
              <td class="overflow-hidden px-3 py-2">
                <span class="block truncate" :title="r.building">{{ r.building }}</span>
              </td>
              <td class="overflow-hidden px-3 py-2">
                <span class="block truncate" :title="r.acmType">{{ r.acmType }}</span>
              </td>
              <td class="overflow-hidden px-3 py-2 text-rag-red">
                <span class="block truncate" :title="r.errorDetail ?? ''">{{ r.errorDetail }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Confirming — progress while import runs -->
    <div v-else-if="step === 'confirming'" class="py-4">
      <p class="mb-4 text-sm font-semibold text-jl-navy">Importing entries…</p>
      <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>Creating sites and ACM entries…</span>
        <span class="font-semibold">{{ Math.round(bulk.progress.value) }}%</span>
      </div>
      <div class="mb-2 h-3 overflow-hidden rounded-full bg-slate-200">
        <div class="h-full rounded-full bg-jl-teal" :style="progressBarStyle" />
      </div>
    </div>

    <!-- Step 4: success -->
    <div v-else-if="step === 4 && bulk.importSummary.value" class="py-6 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rag-green-bg text-2xl text-jl-green-dark">✓</div>
      <p class="font-semibold text-jl-navy">Import complete</p>
      <p class="text-sm text-slate-500">
        {{ bulk.importSummary.value.importedEntries }} entries imported · {{ bulk.importSummary.value.createdSites }} new site(s) created.
        All imports logged in each site's Audit Trail.
      </p>
    </div>

    <!-- Error state -->
    <div v-else-if="step === 'error'" class="py-6 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rag-red-bg text-2xl text-rag-red">✕</div>
      <p class="font-semibold text-jl-navy">Something went wrong</p>
      <p class="text-sm text-slate-500">{{ bulk.errorMessage.value }}</p>
    </div>

    <template #footer>
      <!-- Step 1 -->
      <template v-if="step === 1">
        <BaseButton variant="secondary" @click="emit('close')">Cancel</BaseButton>
        <BaseButton :disabled="!file" @click="validate">Validate</BaseButton>
      </template>
      <!-- Stay/go choice or waiting -->
      <template v-else-if="step === 'go-or-stay' || step === 'progress'">
        <!-- no footer buttons — choices are inline -->
      </template>
      <!-- Step 2: validation results -->
      <template v-else-if="step === 2">
        <BaseButton variant="secondary" @click="startOver">Start over</BaseButton>
        <BaseButton :disabled="bulk.result.value?.validCount === 0" @click="bulk.confirmImport()">Confirm Import</BaseButton>
      </template>
      <!-- Confirming -->
      <template v-else-if="step === 'confirming'">
        <!-- no action while import runs -->
      </template>
      <!-- Done or error -->
      <template v-else>
        <BaseButton variant="secondary" v-if="step === 'error'" @click="startOver">Try again</BaseButton>
        <BaseButton @click="emit('close')">{{ step === 4 ? 'Done' : 'Close' }}</BaseButton>
      </template>
    </template>
  </BaseModal>
</template>
