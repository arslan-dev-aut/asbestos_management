<script setup lang="ts">
import { ref } from 'vue'
import { ACCEPTED_FILE_TYPES, ACCEPTED_FILE_EXT } from '@/utils/const'
import { notify } from '@/utils/notify'

withDefaults(defineProps<{ hint?: string; compact?: boolean }>(), {
  hint: 'PDF, JPEG, PNG',
  compact: false,
})
const emit = defineEmits<{ files: [File[]] }>()

const dragging = ref(false)
const input = ref<HTMLInputElement | null>(null)

function validate(files: File[]): File[] {
  const ok: File[] = []
  for (const f of files) {
    if (ACCEPTED_FILE_TYPES.includes(f.type) || /\.(pdf|jpe?g|png)$/i.test(f.name)) ok.push(f)
    else notify.error(`${f.name}: unsupported file type. PDF, JPEG, PNG only.`)
  }
  return ok
}
function onDrop(e: DragEvent) {
  dragging.value = false
  const files = validate(Array.from(e.dataTransfer?.files ?? []))
  if (files.length) emit('files', files)
}
function onPick(e: Event) {
  const files = validate(Array.from((e.target as HTMLInputElement).files ?? []))
  if (files.length) emit('files', files)
  if (input.value) input.value.value = ''
}
</script>

<template>
  <div
    class="cursor-pointer rounded-lg border-2 border-dashed text-center transition"
    :class="[
      dragging ? 'border-jl-teal bg-jl-teal/5' : 'border-slate-300 bg-slate-50/50',
      compact ? 'px-4 py-6' : 'px-6 py-8',
    ]"
    @click="input?.click()"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <div class="text-2xl text-jl-teal">⬆</div>
    <p class="mt-1 text-sm font-semibold text-jl-navy">
      <slot name="title">Drag &amp; drop files here, or click to browse</slot>
    </p>
    <p class="text-xs text-slate-400">{{ hint }}</p>
    <input ref="input" type="file" multiple :accept="ACCEPTED_FILE_EXT" class="hidden" @change="onPick" />
  </div>
</template>
