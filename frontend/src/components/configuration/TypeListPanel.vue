<script setup lang="ts">
import { ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseToggle from '@/components/base/BaseToggle.vue'
import Spinner from '@/components/base/Spinner.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import { notify } from '@/utils/notify'
import type { BuildingType, AcmType } from '@/types'

type TypeItem = BuildingType | AcmType

// onAdd/onToggle are async callbacks (not emits) so we can await the real
// backend round-trip and show loading state for its actual duration.
const props = defineProps<{
  items: TypeItem[]
  placeholder: string
  noun: string // "building type" | "ACM type"
  onAdd: (name: string) => Promise<void>
  onToggle: (id: string, isActive: boolean) => Promise<void>
}>()

const newName = ref('')
const saving = ref(false)
const togglingId = ref<string | null>(null)
const pendingDeactivate = ref<TypeItem | null>(null)

async function add() {
  const name = newName.value.trim()
  if (!name) return
  if (props.items.some((t) => t.name.toLowerCase() === name.toLowerCase())) {
    notify.error(`That ${props.noun} already exists.`)
    return
  }
  saving.value = true
  try {
    await props.onAdd(name)
    newName.value = ''
  } finally {
    saving.value = false
  }
}

async function runToggle(id: string, isActive: boolean) {
  togglingId.value = id
  try {
    await props.onToggle(id, isActive)
  } finally {
    togglingId.value = null
  }
}

function onToggle(item: TypeItem) {
  if (item.isActive) {
    // Deactivation requires confirmation
    pendingDeactivate.value = item
  } else {
    // Reactivation: no confirmation
    runToggle(item.id, true)
  }
}
function confirmDeactivate() {
  const item = pendingDeactivate.value
  pendingDeactivate.value = null
  if (item) runToggle(item.id, false)
}
</script>

<template>
  <div class="max-w-2xl">
    <!-- Add row -->
    <div class="mb-4 flex gap-3">
      <input v-model="newName" class="jl-input" :placeholder="placeholder" @keyup.enter="add" />
      <BaseButton :disabled="!newName.trim()" :loading="saving" @click="add">+ Add New</BaseButton>
    </div>

    <!-- List -->
    <div class="jl-card divide-y divide-slate-100">
      <div
        v-for="item in items"
        :key="item.id"
        class="flex items-center justify-between px-4 py-3"
      >
        <span class="min-w-0 truncate font-semibold" :class="item.isActive ? 'text-jl-navy' : 'text-slate-400'" :title="item.name">
          {{ item.name }}
        </span>
        <Spinner v-if="togglingId === item.id" :size="20" class="text-jl-teal" />
        <BaseToggle v-else :model-value="item.isActive" :disabled="!!togglingId" @update:model-value="onToggle(item)" />
      </div>
      <p v-if="!items.length" class="px-4 py-6 text-center text-sm text-slate-400">No {{ noun }}s yet.</p>
    </div>

    <ConfirmDialog
      v-if="pendingDeactivate"
      title="Deactivate this type?"
      :message="`'${pendingDeactivate.name}' will no longer appear in dropdowns when creating new ACM entries. Existing entries using it are unchanged.`"
      confirm-label="Deactivate"
      @confirm="confirmDeactivate"
      @cancel="pendingDeactivate = null"
    />
  </div>
</template>
