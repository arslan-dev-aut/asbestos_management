<script setup lang="ts">
import BaseButton from './BaseButton.vue'

defineProps<{ title: string; message: string; confirmLabel?: string; cancelLabel?: string }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <div class="fixed inset-0 z-[60] flex items-center justify-center bg-jl-navy/60 p-4">
    <div class="jl-card w-full max-w-md p-6">
      <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-rag-amber-bg text-xl text-jl-orange">⚠</div>
      <h3 class="mb-2 text-lg font-bold text-jl-navy">{{ title }}</h3>
      <p class="mb-6 text-sm text-slate-500">{{ message }}</p>
      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" @click="emit('cancel')">{{ cancelLabel ?? 'Cancel' }}</BaseButton>
        <BaseButton variant="dark" @click="emit('confirm')">{{ confirmLabel ?? 'Confirm' }}</BaseButton>
      </div>
    </div>
  </div>
</template>
