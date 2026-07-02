<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ pageIndex: number; pageSize: number; totalCount: number }>()
const emit = defineEmits<{ 'update:pageIndex': [number] }>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.totalCount / props.pageSize)))
const from = computed(() => (props.totalCount === 0 ? 0 : props.pageIndex * props.pageSize + 1))
const to = computed(() => Math.min(props.totalCount, (props.pageIndex + 1) * props.pageSize))

function go(i: number) {
  if (i >= 0 && i < totalPages.value) emit('update:pageIndex', i)
}
</script>

<template>
  <div class="flex items-center justify-between px-1 py-3 text-sm text-slate-500">
    <span>Showing {{ from }}–{{ to }} of {{ totalCount }}</span>
    <div class="flex items-center gap-1">
      <button class="rounded border border-slate-200 px-2.5 py-1 disabled:opacity-40" :disabled="pageIndex === 0" @click="go(pageIndex - 1)">‹ Prev</button>
      <button
        v-for="i in totalPages"
        :key="i"
        class="min-w-8 rounded border px-2.5 py-1"
        :class="i - 1 === pageIndex ? 'border-jl-teal bg-jl-teal text-white' : 'border-slate-200 hover:bg-slate-50'"
        @click="go(i - 1)"
      >
        {{ i }}
      </button>
      <button class="rounded border border-slate-200 px-2.5 py-1 disabled:opacity-40" :disabled="pageIndex >= totalPages - 1" @click="go(pageIndex + 1)">Next ›</button>
    </div>
  </div>
</template>
