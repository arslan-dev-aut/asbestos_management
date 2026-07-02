<script setup lang="ts">
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
const router = useRouter()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-32 text-center">
    <h1 class="text-5xl font-bold text-jl-navy">404</h1>
    <p class="mt-2 text-slate-500">The page you’re looking for doesn’t exist.</p>
    <BaseButton class="mt-6" @click="router.push('/asbestos-register')">Back to Register</BaseButton>
  </div>
</template>
