<script setup lang="ts">
import { toasts, dismiss, type ToastType } from '@/utils/notify'

const styles: Record<ToastType, string> = {
  success: 'border-rag-green bg-rag-green-bg text-jl-green-dark',
  error: 'border-rag-red bg-rag-red-bg text-rag-red',
  info: 'border-jl-teal bg-jl-teal/10 text-jl-teal-dark',
  warning: 'border-rag-amber bg-rag-amber-bg text-jl-orange',
}
const icons: Record<ToastType, string> = {
  success: '✓', error: '✕', info: 'ℹ', warning: '⚠',
}
</script>

<template>
  <div class="pointer-events-none fixed right-4 top-4 z-[100] flex flex-col gap-2">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="pointer-events-auto flex min-w-[260px] max-w-sm items-start gap-2 rounded-md border-l-4 bg-white px-4 py-3 text-sm font-medium shadow-lg"
      :class="styles[t.type]"
    >
      <span>{{ icons[t.type] }}</span>
      <span class="flex-1">{{ t.message }}</span>
      <button class="text-slate-400 hover:text-slate-600" @click="dismiss(t.id)">✕</button>
    </div>
  </div>
</template>
