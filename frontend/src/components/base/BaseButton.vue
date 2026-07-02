<script setup lang="ts">
import Spinner from './Spinner.vue'

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'dark' | 'ghost' | 'orange' | 'danger'
    size?: 'sm' | 'md'
    disabled?: boolean
    loading?: boolean
    type?: 'button' | 'submit'
  }>(),
  { variant: 'primary', size: 'md', disabled: false, loading: false, type: 'button' },
)

const base =
  'inline-flex items-center justify-center gap-2 rounded-md font-semibold transition focus:outline-none disabled:cursor-not-allowed disabled:opacity-50'

const variants: Record<string, string> = {
  primary: 'bg-jl-green text-white hover:bg-jl-green-dark',
  secondary: 'border border-slate-300 bg-white text-jl-navy hover:bg-slate-50',
  dark: 'bg-jl-navy text-white hover:bg-jl-navy-dark',
  ghost: 'text-jl-teal hover:text-jl-teal-dark hover:underline',
  orange: 'bg-jl-orange text-white hover:brightness-95',
  danger: 'bg-rag-red text-white hover:brightness-95',
}
const sizes: Record<string, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
}
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[base, variants[$props.variant ?? 'primary'], sizes[$props.size ?? 'md']]"
  >
    <Spinner v-if="loading" :size="size === 'sm' ? 14 : 16" />
    <slot />
  </button>
</template>
