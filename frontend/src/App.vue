<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import ToastHost from '@/components/base/ToastHost.vue'

const route = useRoute()
// Public QR page renders without the JobLogic app shell
const isPublic = computed(() => route.meta.public === true)
</script>

<template>
  <ToastHost />
  <template v-if="isPublic">
    <RouterView />
  </template>
  <AppShell v-else>
    <RouterView />
  </AppShell>
</template>
