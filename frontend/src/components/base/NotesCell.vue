<script setup lang="ts">
import { ref, computed } from 'vue'

// Notes display: truncate after 100 chars with ellipsis; click to expand /
// collapse; full text also available as a hover tooltip. Used everywhere the
// ACM entries table appears (Register, View-Only portals, QR page).
const props = defineProps<{ notes: string | null }>()

const LIMIT = 100
const expanded = ref(false)
const isLong = computed(() => (props.notes?.length ?? 0) > LIMIT)
const display = computed(() => {
  if (!props.notes) return '—'
  if (expanded.value || !isLong.value) return props.notes
  return props.notes.slice(0, LIMIT) + '…'
})
</script>

<template>
  <span v-if="!notes" class="text-slate-400">—</span>
  <span v-else class="text-slate-500" :title="notes">
    {{ display }}
    <button
      v-if="isLong"
      class="ml-1 text-xs font-semibold text-jl-teal hover:underline"
      @click.stop="expanded = !expanded"
    >
      {{ expanded ? 'less' : 'more' }}
    </button>
  </span>
</template>
