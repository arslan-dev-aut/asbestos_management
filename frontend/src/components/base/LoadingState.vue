<script setup lang="ts">
withDefaults(defineProps<{ message?: string }>(), {
  message: 'Loading…',
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 py-16">
    <span class="animate-pulse text-5xl leading-none text-jl-teal">◆</span>
    <p class="text-sm text-slate-400">{{ message }}</p>
  </div>
</template>
