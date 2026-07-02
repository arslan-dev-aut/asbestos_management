<script setup lang="ts">
import { useBulkJob } from '@/composables/useBulkJob'

// JobLogic application shell — left sidebar + topbar.
// Static chrome to mirror the prototype; only the Settings area is functional.
const navItems = [
  'Dashboard', 'Customers', 'Sites', 'Assets', 'Projects', 'Jobs', 'Quotes',
  'Invoices', 'PPM', 'Hire Contracts', 'Purchasing', 'Reports', 'Engineers',
  'Forms Logbook', 'Refcom', 'Stock', 'Marketplace', 'Certificates',
]

const bulk = useBulkJob()

</script>

<template>
  <div class="flex h-full">
    <!-- Sidebar -->
    <aside class="hidden w-56 shrink-0 flex-col bg-jl-navy text-white md:flex">
      <div class="flex items-center gap-2 px-5 py-4 text-xl font-bold">
        <span class="text-jl-teal">◆</span> joblogic
      </div>
      <nav class="flex-1 overflow-y-auto py-2 text-sm">
        <a
          v-for="item in navItems"
          :key="item"
          class="flex cursor-pointer items-center gap-3 px-5 py-2.5 text-slate-300 hover:bg-white/5"
        >
          {{ item }}
        </a>
        <a class="flex cursor-pointer items-center gap-3 bg-jl-teal px-5 py-2.5 font-semibold text-white">
          Settings
        </a>
      </nav>
    </aside>

    <!-- Main column -->
    <div class="flex min-w-0 flex-1 flex-col">
      <!-- Topbar -->
      <header class="flex h-16 shrink-0 items-center justify-end gap-4 bg-white px-6 shadow-sm">

        <!-- Global bulk upload status pill — visible app-wide while a job is active -->
        <button
          v-if="bulk.isActive.value"
          class="flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition-colors"
          :class="bulk.pillClass.value"
          :title="bulk.isBusy.value ? 'Bulk upload in progress — click to open' : 'Click to open bulk upload'"
          @click="bulk.requestOpenModal()"
        >
          <!-- Spinner while busy, dot when done/validated -->
          <span v-if="bulk.isBusy.value" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          <span v-else class="h-2 w-2 rounded-full bg-current" />
          {{ bulk.pillLabel.value }}
          <!-- Mini progress bar underneath the label text -->
          <span v-if="bulk.isBusy.value" class="relative ml-1 inline-block h-1.5 w-12 overflow-hidden rounded-full bg-current/20">
            <span
              class="absolute inset-y-0 left-0 rounded-full bg-current"
              :style="{ width: `${bulk.progress.value}%`, transition: 'width 0.15s ease-out' }"
            />
          </span>
        </button>

        <button class="rounded-full bg-jl-teal px-4 py-1.5 text-sm font-semibold text-white">
          🎁 Refer &amp; Earn
        </button>
        <span class="text-slate-400">🔍</span>
        <span class="text-slate-400">💬</span>
        <span class="relative text-slate-400">
          🔔
          <span class="absolute -right-1 -top-1 rounded-full bg-rag-red px-1 text-[10px] text-white">23</span>
        </span>
        <button class="rounded bg-jl-navy px-3 py-1.5 text-sm font-semibold text-white">? Help</button>
        <div class="flex h-8 w-8 items-center justify-center rounded-full bg-jl-teal text-sm font-bold text-white">A</div>
      </header>

      <!-- Routed content -->
      <main class="flex-1 overflow-y-auto px-6 py-6">
        <slot />
      </main>
    </div>
  </div>
</template>
