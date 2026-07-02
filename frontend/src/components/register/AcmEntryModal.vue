<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import BaseToggle from '@/components/base/BaseToggle.vue'
import FileDropzone from '@/components/base/FileDropzone.vue'
import AttachmentList from '@/components/documents/AttachmentList.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import * as reg from '@/services/register.service'
import { getBuildingTypes, getAcmTypes } from '@/services/configuration.service'
import { conditions, riskScores } from '@/utils/const'
import { notify } from '@/utils/notify'
import type { AcmEntry, LookupOption, BuildingType, AcmType, Condition, RiskScore } from '@/types'

const props = defineProps<{
  mode: 'add' | 'edit' | 'view'
  asbestosSiteId: string
  siteId: string   // Joblogic site GUID — needed for the assets lookup
  siteName: string
  entry?: AcmEntry | null
}>()
const emit = defineEmits<{ close: []; saved: []; statusChanged: [] }>()

const readonly = computed(() => props.mode === 'view')
const titleMap = { add: 'Add ACM Entry', edit: 'Edit ACM Entry', view: 'ACM Entry' }
const eyebrowMap = { add: 'Add Entry', edit: 'Edit Entry', view: 'View Entry' }

// Form state
const buildingTypeId = ref(props.entry?.buildingTypeId ?? null)
const roomLocation = ref(props.entry?.roomLocation ?? '')
const assetId = ref(props.entry?.assetId ?? null)
const acmTypeId = ref(props.entry?.acmTypeId ?? null)
const condition = ref<Condition | null>(props.entry?.condition ?? null)
const riskScore = ref<RiskScore | null>(props.entry?.riskScore ?? null)
const notes = ref(props.entry?.notes ?? '')
const NOTES_MAX = 250

// Local caches of loaded options — needed so buildInput() can resolve names.
const buildingTypes = ref<BuildingType[]>([])
const acmTypes = ref<AcmType[]>([])
const assets = ref<LookupOption[]>([])

// Loaders called on first open of each dropdown.
async function loadBuildingTypes() {
  const items = await getBuildingTypes(true)
  buildingTypes.value = items
  // Pre-seed selected label for edit/view mode where entry already has a value.
  return items.map((b) => ({ value: b.id, label: b.name }))
}
async function loadAcmTypes() {
  const items = await getAcmTypes(true)
  acmTypes.value = items
  return items.map((a) => ({ value: a.id, label: a.name }))
}
async function loadAssets() {
  const items = await reg.getAssetsBySite(props.siteId)
  assets.value = items
  return items.map((a) => ({ value: a.id, label: a.name }))
}

// In edit/view mode the ACM list API returns building/ACM type NAMES only
// (no IDs), so the form starts with empty IDs and Save would stay disabled.
// Pre-load both type lists and resolve the IDs from the entry's names.
onMounted(async () => {
  if (props.mode === 'add' || !props.entry) return
  try {
    const [bts, ats] = await Promise.all([getBuildingTypes(true), getAcmTypes(true)])
    buildingTypes.value = bts
    acmTypes.value = ats
    if (!buildingTypeId.value) {
      buildingTypeId.value = bts.find((b) => b.name === props.entry?.buildingTypeName)?.id ?? buildingTypeId.value
    }
    if (!acmTypeId.value) {
      acmTypeId.value = ats.find((a) => a.name === props.entry?.acmTypeName)?.id ?? acmTypeId.value
    }
  } catch {
    // Non-fatal — the user can still re-pick from the dropdowns.
  }
})

// Staged attachments
const stagedFiles = ref<{ fileName: string; file: File }[]>([])
function onFiles(files: File[]) {
  for (const f of files) {
    stagedFiles.value.push({ fileName: f.name, file: f })
  }
}
function removeStaged(i: number) { stagedFiles.value.splice(i, 1) }

const removedAttachmentIds = ref<string[]>([])
function removeExisting(id: string) { removedAttachmentIds.value.push(id) }
const visibleExisting = computed(() =>
  (props.entry?.attachments ?? []).filter((a) => !removedAttachmentIds.value.includes(a.id)),
)

const saving = ref<'save' | 'saveAnother' | false>(false)
const pendingStatus = ref(false)

const canSave = computed(
  () => !!buildingTypeId.value && !!roomLocation.value.trim() && !!acmTypeId.value && !!condition.value && !!riskScore.value && saving.value === false,
)

function buildInput(): reg.AcmEntryInput {
  // Resolve names from cached loaded options; fall back to entry names for edit/view.
  const buildingTypeName =
    buildingTypes.value.find((b) => b.id === buildingTypeId.value)?.name ??
    props.entry?.buildingTypeName ?? ''
  const acmTypeName =
    acmTypes.value.find((a) => a.id === acmTypeId.value)?.name ??
    props.entry?.acmTypeName ?? ''
  return {
    buildingTypeId: buildingTypeId.value!,
    buildingTypeName,
    roomLocation: roomLocation.value.trim(),
    assetId: assetId.value,
    acmTypeId: acmTypeId.value!,
    acmTypeName,
    condition: condition.value!,
    riskScore: riskScore.value!,
    notes: notes.value.trim() || null,
    newAttachments: [...stagedFiles.value],
    removedAttachmentIds: [...removedAttachmentIds.value],
  }
}

function resetForm() {
  buildingTypeId.value = null
  roomLocation.value = ''
  assetId.value = null
  acmTypeId.value = null
  condition.value = null
  riskScore.value = null
  notes.value = ''
  stagedFiles.value = []
  removedAttachmentIds.value = []
}

async function save(addAnother = false) {
  if (!canSave.value) { notify.error('Please complete all required fields.'); return }
  saving.value = addAnother ? 'saveAnother' : 'save'
  try {
    if (props.mode === 'edit' && props.entry) {
      await reg.updateAcmEntry(props.asbestosSiteId, props.entry.id, buildInput())
      notify.success('ACM entry updated.')
    } else {
      await reg.addAcmEntry(props.asbestosSiteId, buildInput())
      notify.success('ACM entry added.')
    }
    emit('saved')
    if (addAnother) resetForm()
    else emit('close')
  } finally {
    saving.value = false
  }
}

function onToggleStatus() {
  if (props.entry?.status === 'ACTIVE') pendingStatus.value = true
  else doToggle('ACTIVE')
}
const toggling = ref(false)
async function doToggle(status: AcmEntry['status']) {
  if (!props.entry) return
  toggling.value = true
  try {
    await reg.toggleAcmStatus(props.asbestosSiteId, props.entry.id, status)
    pendingStatus.value = false
    notify.success(status === 'REMEDIATED' ? 'Entry marked as Remediated.' : 'Entry reactivated.')
    emit('statusChanged')
    emit('close')
  } finally {
    toggling.value = false
  }
}

// Pre-seed options for edit/view mode so the selected label shows immediately.
// Use the live resolved id (back-filled on mount) keyed to the entry name, so
// the dropdown shows the correct label even before its own loader runs.
const buildingTypeInitial = computed(() =>
  props.entry ? [{ value: buildingTypeId.value ?? props.entry.buildingTypeId, label: props.entry.buildingTypeName }] : [],
)
const acmTypeInitial = computed(() =>
  props.entry ? [{ value: acmTypeId.value ?? props.entry.acmTypeId, label: props.entry.acmTypeName }] : [],
)
</script>

<template>
  <BaseModal :eyebrow="eyebrowMap[mode]" :title="titleMap[mode]" :subtitle="siteName" wide @close="emit('close')">
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="jl-label">Building <span v-if="!readonly" class="text-rag-red">*</span></label>
        <BaseSelect
          v-model="buildingTypeId"
          :disabled="readonly"
          placeholder="Select building..."
          :options="buildingTypeInitial"
          :loader="readonly ? undefined : loadBuildingTypes"
        />
      </div>
      <div>
        <label class="jl-label">Room / Location <span v-if="!readonly" class="text-rag-red">*</span></label>
        <input v-model="roomLocation" :readonly="readonly" class="jl-input" placeholder="e.g. Basement pipework" />
      </div>
      <div>
        <label class="jl-label">Asset</label>
        <BaseSelect
          v-model="assetId"
          :disabled="readonly"
          placeholder="Link an asset (optional)..."
          :options="[]"
          :loader="readonly ? undefined : loadAssets"
        />
      </div>
      <div>
        <label class="jl-label">ACM Type <span v-if="!readonly" class="text-rag-red">*</span></label>
        <BaseSelect
          v-model="acmTypeId"
          :disabled="readonly"
          placeholder="Select ACM type..."
          :options="acmTypeInitial"
          :loader="readonly ? undefined : loadAcmTypes"
        />
      </div>
      <div>
        <label class="jl-label">Condition <span v-if="!readonly" class="text-rag-red">*</span></label>
        <BaseSelect v-model="condition" :disabled="readonly" placeholder="Select condition..." :searchable="false" :options="conditions.map((c) => ({ value: c.value, label: c.label }))" />
      </div>
      <div>
        <label class="jl-label">Risk Score <span v-if="!readonly" class="text-rag-red">*</span></label>
        <BaseSelect v-model="riskScore" :disabled="readonly" placeholder="Select risk..." :searchable="false" :options="riskScores.map((r) => ({ value: r.value, label: r.label }))" />
      </div>
    </div>

    <div class="mt-4">
      <label class="jl-label">Notes</label>
      <textarea
        v-model="notes"
        :readonly="readonly"
        :maxlength="NOTES_MAX"
        rows="2"
        class="jl-input resize-y"
        placeholder="e.g. Do not disturb. Encapsulated."
      />
      <p v-if="!readonly" class="mt-1 text-right text-xs text-slate-400">{{ notes.length }} / {{ NOTES_MAX }}</p>
    </div>

    <!-- Attachments -->
    <div class="mt-4">
      <label class="jl-label">Attachments</label>
      <p class="mb-2 text-xs text-slate-400">Entry-specific photos or documents. PDF, JPEG, PNG only.</p>
      <FileDropzone v-if="!readonly" compact @files="onFiles">
        <template #title>Add photos or documents</template>
      </FileDropzone>
      <AttachmentList
        :existing="visibleExisting"
        :staged="stagedFiles"
        :readonly="readonly"
        :asbestos-site-id="asbestosSiteId"
        :acm-entry-id="entry?.id"
        @remove-staged="removeStaged"
        @remove-existing="removeExisting"
      />
    </div>

    <!-- Status toggle (edit mode only) -->
    <div v-if="mode === 'edit' && entry" class="mt-5 flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
      <div>
        <p class="text-sm font-semibold text-jl-navy">Status: {{ entry.status === 'ACTIVE' ? 'Active' : 'Remediated' }}</p>
        <p class="text-xs text-slate-400">Appears on mobile acknowledgement screens.</p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="toggling" class="text-xs text-slate-400 animate-pulse">Saving…</span>
        <BaseToggle :model-value="entry.status === 'ACTIVE'" :disabled="toggling" @update:model-value="onToggleStatus" />
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">{{ readonly ? 'Close' : 'Cancel' }}</BaseButton>
      <template v-if="mode === 'add'">
        <BaseButton variant="secondary" :disabled="!canSave" :loading="saving === 'saveAnother'" @click="save(true)">Save &amp; Add Another</BaseButton>
        <BaseButton :disabled="!canSave" :loading="saving === 'save'" @click="save(false)">Save</BaseButton>
      </template>
      <BaseButton v-else-if="mode === 'edit'" :disabled="!canSave" :loading="saving === 'save'" @click="save(false)">Save</BaseButton>
    </template>
  </BaseModal>

  <ConfirmDialog
    v-if="pendingStatus"
    title="Mark this entry as Remediated?"
    message="This entry will no longer appear on mobile acknowledgement screens for engineers visiting this site. The record will be preserved for audit purposes."
    @confirm="doToggle('REMEDIATED')"
    @cancel="pendingStatus = false"
  />
</template>
