<script setup lang="ts">
// Lightweight inline SVG line-icon set. Add new icons to `paths` as needed.
// Stroke-based (1.6) to match the JobLogic line-icon look.
withDefaults(
  defineProps<{
    name: 'download' | 'upload' | 'search' | 'reset' | 'plus' | 'external' | 'qr' | 'eye' | 'trash' | 'pencil' | 'paperclip' | 'file'
    size?: number
    strokeWidth?: number
  }>(),
  { size: 16, strokeWidth: 1.8 },
)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <!-- download: down arrow over a short underline -->
    <template v-if="name === 'download'">
      <path d="M12 4v10" />
      <path d="m8 11 4 3 4-3" />
      <path d="M7 19h10" />
    </template>
    <!-- upload: up arrow over a short underline -->
    <template v-else-if="name === 'upload'">
      <path d="M12 14V4" />
      <path d="m8 7 4-3 4 3" />
      <path d="M7 19h10" />
    </template>
    <!-- search: magnifier -->
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </template>
    <!-- reset: circular refresh arrow -->
    <template v-else-if="name === 'reset'">
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
    </template>
    <!-- plus -->
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </template>
    <!-- external link -->
    <template v-else-if="name === 'external'">
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </template>
    <!-- qr: 2x2 grid of squares (QR-style) -->
    <template v-else-if="name === 'qr'">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </template>
    <!-- eye: view -->
    <template v-else-if="name === 'eye'">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </template>
    <!-- trash: remove -->
    <template v-else-if="name === 'trash'">
      <path d="M3 6h18" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M10 11v6" /><path d="M14 11v6" />
    </template>
    <!-- pencil: edit (diagonal pencil over a short underline) -->
    <template v-else-if="name === 'pencil'">
      <path d="M16.5 4.5a2.1 2.1 0 0 1 3 3L9 18l-4 1 1-4Z" />
      <path d="M5 21h7" />
    </template>
    <!-- paperclip: attachment -->
    <template v-else-if="name === 'paperclip'">
      <path d="M21.4 11.05 12.25 20.2a5 5 0 0 1-7.07-7.07l9.19-9.19a3.33 3.33 0 0 1 4.71 4.71l-9.2 9.19a1.67 1.67 0 0 1-2.36-2.36l8.49-8.48" />
    </template>
    <!-- file: document -->
    <template v-else-if="name === 'file'">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
    </template>
  </svg>
</template>
