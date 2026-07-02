<script setup lang="ts">
defineProps<{ eyebrow?: string; title: string; subtitle?: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-jl-navy/60 p-4 py-10">
    <div class="jl-card w-full" :class="wide ? 'max-w-3xl' : 'max-w-xl'">
      <header class="flex items-start justify-between border-b border-slate-100 px-6 py-4">
        <div>
          <p v-if="eyebrow" class="text-xs font-bold uppercase tracking-widest text-jl-teal">{{ eyebrow }}</p>
          <h2 class="text-xl font-bold text-jl-navy">{{ title }}</h2>
          <p v-if="subtitle" class="text-sm text-slate-500">{{ subtitle }}</p>
        </div>
        <button class="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" @click="emit('close')">✕</button>
      </header>
      <div class="px-6 py-5">
        <slot />
      </div>
      <footer v-if="$slots.footer" class="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>
