<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'

interface Option { value: string; label: string; disabled?: boolean }

const props = withDefaults(
  defineProps<{
    modelValue: string | null
    options?: Option[]
    placeholder?: string
    searchable?: boolean
    disabled?: boolean
    serverSearch?: boolean
    searching?: boolean
    // Async loader: called once on first open. Replaces the static options list.
    loader?: () => Promise<Option[]>
  }>(),
  { options: () => [], placeholder: 'Please select option(s)', searchable: true, disabled: false, serverSearch: false, searching: false },
)
const emit = defineEmits<{
  'update:modelValue': [string | null]
  'search': [string]
}>()

const open = ref(false)
const search = ref('')
const root = ref<HTMLElement | null>(null)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Lazy-loaded options (populated on first open when loader prop is provided).
const loadedOptions = ref<Option[]>([])
const loadingOptions = ref(false)
const loaderCalled = ref(false)

const allOptions = computed(() => loadedOptions.value.length ? loadedOptions.value : props.options)
const selectedLabel = computed(() => allOptions.value.find((o) => o.value === props.modelValue)?.label ?? '')
const filtered = computed(() => {
  // Labels can be null/undefined (e.g. a site with no name in the source data) —
  // coerce to '' before sorting/filtering so a bad row can't crash the render.
  const sorted = [...allOptions.value].sort((a, b) => (a.label ?? '').localeCompare(b.label ?? ''))
  if (!props.searchable || props.serverSearch || !search.value) return sorted
  return sorted.filter((o) => (o.label ?? '').toLowerCase().includes(search.value.toLowerCase()))
})

watch(search, (val) => {
  if (!props.serverSearch) return
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => emit('search', val), 300)
})

function select(o: Option) {
  if (o.disabled) return
  emit('update:modelValue', o.value)
  open.value = false
  search.value = ''
}
async function toggle() {
  if (props.disabled) return
  open.value = !open.value
  // Fetch options on first open if a loader is provided.
  if (open.value && props.loader && !loaderCalled.value) {
    loaderCalled.value = true
    loadingOptions.value = true
    try {
      loadedOptions.value = await props.loader()
    } finally {
      loadingOptions.value = false
    }
  }
}
function onPointerDownOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}
// Use mousedown (fires before the button's click) on the document so the
// outside-click close never races with the toggle's own click event.
onMounted(() => document.addEventListener('mousedown', onPointerDownOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onPointerDownOutside))
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition flex items-center justify-between text-left focus:border-jl-teal focus:ring-2 focus:ring-jl-teal/20"
      :class="disabled ? 'bg-slate-50 text-jl-navy cursor-default' : 'bg-white cursor-pointer'"
      @click.stop="toggle"
    >
      <span class="min-w-0 truncate" :class="selectedLabel ? 'text-jl-navy' : 'text-slate-400'" :title="selectedLabel || undefined">
        {{ selectedLabel || placeholder }}
      </span>
      <span class="ml-1 shrink-0 text-slate-400">▾</span>
    </button>

    <div
      v-if="open"
      class="absolute z-30 mt-1 max-h-64 w-full overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg"
    >
      <div v-if="searchable" class="border-b border-slate-100 p-2">
        <input v-model="search" class="jl-input py-1.5 text-xs" :placeholder="serverSearch ? 'Type to search…' : 'Search...'" @click.stop />
      </div>
      <ul class="max-h-52 overflow-y-auto py-1 text-sm">
        <li v-if="searching || loadingOptions" class="px-3 py-2 text-slate-400">Loading…</li>
        <template v-else>
          <li
            v-for="o in filtered"
            :key="o.value"
            class="cursor-pointer px-3 py-2 hover:bg-jl-teal/10"
            :class="{
              'bg-jl-teal/10 font-semibold': o.value === modelValue,
              'cursor-not-allowed text-slate-300 hover:bg-transparent': o.disabled,
            }"
            @click="select(o)"
          >
            <span class="block truncate" :title="o.label">{{ o.label }}</span>
          </li>
          <li v-if="!filtered.length" class="px-3 py-2 text-slate-400">
            {{ serverSearch && !search ? 'Type to search customers…' : 'No options' }}
          </li>
        </template>
      </ul>
    </div>
  </div>
</template>
