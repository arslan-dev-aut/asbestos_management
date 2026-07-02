<script setup lang="ts">
import { computed } from 'vue'

// Dot-ring spinner. `size` in px controls the ring; `color` is any CSS colour
// (defaults to currentColor so it inherits the button/text colour).
const props = withDefaults(defineProps<{ size?: number; color?: string }>(), {
  size: 18,
  color: 'currentColor',
})

const dotSize = computed(() => Math.max(2, props.size * 0.22))
const radius = computed(() => props.size / 2 - dotSize.value / 2)

// 8 dots evenly around the ring, each with a staggered fade for the trail.
const dots = computed(() =>
  Array.from({ length: 8 }, (_, i) => ({
    transform: `translate(-50%, -50%) rotate(${i * 45}deg) translateY(-${radius.value}px)`,
    opacity: 0.15 + (i / 8) * 0.85,
  })),
)
</script>

<template>
  <span
    class="jl-spinner inline-block align-[-0.2em]"
    :style="{ width: `${size}px`, height: `${size}px`, color }"
    role="status"
    aria-label="Loading"
  >
    <span
      v-for="(d, i) in dots"
      :key="i"
      class="jl-spinner-dot"
      :style="{ transform: d.transform, opacity: d.opacity, width: `${dotSize}px`, height: `${dotSize}px` }"
    />
  </span>
</template>

<style scoped>
.jl-spinner {
  position: relative;
  animation: jl-spin 0.8s linear infinite;
}
.jl-spinner-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 9999px;
  background: currentColor;
}
@keyframes jl-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
