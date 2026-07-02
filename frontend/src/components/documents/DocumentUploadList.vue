<script setup lang="ts">
import { computed } from 'vue'
import FileDropzone from '@/components/base/FileDropzone.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { documentTypes } from '@/utils/const'
import type { DocType } from '@/types'

// A staged document the user has added but not yet saved.
export interface StagedDoc {
  fileName: string
  docType: DocType
  ampExpiryDate: string // yyyy-mm-dd; only meaningful when docType === 'AMP'
  file: File // raw File object — passed directly to multipart upload
}

const props = defineProps<{ modelValue: StagedDoc[] }>()
const emit = defineEmits<{ 'update:modelValue': [StagedDoc[]] }>()

function onFiles(files: File[]) {
  const added: StagedDoc[] = []
  // Track whether AMP is already taken (existing rows + newly added in this batch).
  let ampTaken = props.modelValue.some((d) => d.docType === 'AMP')
  for (const f of files) {
    const docType: DocType = ampTaken ? 'OTHER' : 'AMP'
    if (docType === 'AMP') ampTaken = true
    added.push({ fileName: f.name, docType, ampExpiryDate: '', file: f })
  }
  emit('update:modelValue', [...props.modelValue, ...added])
}
function setType(i: number, value: string | null) {
  const next = [...props.modelValue]
  next[i] = { ...next[i], docType: (value as DocType) ?? 'OTHER' }
  // AMP-only: clear expiry when switching away from AMP
  if (next[i].docType !== 'AMP') next[i].ampExpiryDate = ''
  emit('update:modelValue', next)
}
function setExpiry(i: number, value: string) {
  const next = [...props.modelValue]
  next[i] = { ...next[i], ampExpiryDate: value }
  emit('update:modelValue', next)
}
function onExpiryInput(i: number, e: Event) {
  setExpiry(i, (e.target as HTMLInputElement).value)
}
function remove(i: number) {
  emit('update:modelValue', props.modelValue.filter((_, idx) => idx !== i))
}

// AMP may only appear once across all staged docs. Once one row has AMP selected,
// all other rows' dropdowns hide the AMP option.
const ampAlreadyUsed = computed(() => props.modelValue.some((d) => d.docType === 'AMP'))

function optionsForRow(i: number) {
  const rowIsAmp = props.modelValue[i]?.docType === 'AMP'
  // Show AMP only for the row that currently has it, or if no row has AMP yet.
  return documentTypes
    .filter((d) => d.value !== 'AMP' || rowIsAmp || !ampAlreadyUsed.value)
    .map((d) => ({ value: d.value, label: d.label }))
}
</script>

<template>
  <div>
    <FileDropzone @files="onFiles" />

    <div v-for="(doc, i) in modelValue" :key="i" class="mt-3 rounded-md border border-slate-200 p-3">
      <div class="flex items-center gap-3">
        <span class="text-rag-red"><BaseIcon name="file" :size="18" /></span>
        <span class="flex-1 truncate text-sm font-medium text-jl-navy">{{ doc.fileName }}</span>
        <div class="w-44">
          <BaseSelect
            :model-value="doc.docType"
            :options="optionsForRow(i)"
            :searchable="false"
            @update:model-value="setType(i, $event)"
          />
        </div>
        <button class="rounded p-1.5 text-slate-600 transition-colors hover:bg-slate-100 hover:text-rag-red" @click="remove(i)"><BaseIcon name="trash" :size="18" :stroke-width="2.2" /></button>
      </div>

      <!-- AMP-only mandatory expiry date -->
      <div v-if="doc.docType === 'AMP'" class="mt-3">
        <label class="jl-label">AMP Expiry Date <span class="text-rag-red">*</span></label>
        <input
          type="date"
          class="jl-input max-w-xs"
          :value="doc.ampExpiryDate"
          @change="onExpiryInput(i, $event)"
        />
        <p class="mt-1 text-xs text-slate-400">
          Set the date this AMP expires. The system will flag sites approaching or past expiry.
        </p>
      </div>
    </div>
  </div>
</template>
