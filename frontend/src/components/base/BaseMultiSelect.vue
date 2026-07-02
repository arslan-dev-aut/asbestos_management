<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

interface Option { value: string; label: string }

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    options: Option[]
    placeholder?: string
    searchable?: boolean
    // When true, typing emits `search` (debounced) for the parent to fetch
    // matching options from the API instead of filtering locally.
    remote?: boolean
    loading?: boolean
  }>(),
  { placeholder: 'Please select option(s)', searchable: true, remote: false, loading: false },
)
const emit = defineEmits<{
  'update:modelValue': [string[]]
  search: [string]
}>()

const open = ref(false)
const search = ref('')
const root = ref<HTMLElement | null>(null)

// Local filtering only when NOT in remote mode — remote shows options as-is.
const filtered = computed(() => {
  const sorted = [...props.options].sort((a, b) => a.label.localeCompare(b.label))
  if (props.remote || !props.searchable || !search.value) return sorted
  return sorted.filter((o) => o.label.toLowerCase().includes(search.value.toLowerCase()))
})
const summary = computed(() => {
  if (!props.modelValue.length) return ''
  if (props.modelValue.length === 1) return props.options.find((o) => o.value === props.modelValue[0])?.label ?? ''
  return `${props.modelValue.length} selected`
})

// Debounce the search emit in remote mode.
let _debounce: ReturnType<typeof setTimeout> | null = null
watch(search, (term) => {
  if (!props.remote) return
  if (_debounce) clearTimeout(_debounce)
  _debounce = setTimeout(() => emit('search', term.trim()), 300)
})

function toggleOption(o: Option) {
  const set = new Set(props.modelValue)
  set.has(o.value) ? set.delete(o.value) : set.add(o.value)
  emit('update:modelValue', [...set])
}
function onClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  if (_debounce) clearTimeout(_debounce)
})
</script>

<template>
  <div ref="root" class="relative">
    <button type="button" class="jl-input flex items-center justify-between text-left" @click="open = !open">
      <span :class="summary ? 'text-jl-navy' : 'text-slate-400'">{{ summary || placeholder }}</span>
      <span class="text-slate-400">▾</span>
    </button>
    <div v-if="open" class="absolute z-30 mt-1 max-h-64 w-full overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
      <div v-if="searchable" class="border-b border-slate-100 p-2">
        <input v-model="search" class="jl-input py-1.5 text-xs" placeholder="Search..." @click.stop />
      </div>
      <ul class="max-h-52 overflow-y-auto py-1 text-sm">
        <li v-if="loading" class="px-3 py-2 text-slate-400">Searching…</li>
        <template v-else>
          <li
            v-for="o in filtered"
            :key="o.value"
            class="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-jl-teal/10"
            @click="toggleOption(o)"
          >
            <input type="checkbox" :checked="modelValue.includes(o.value)" class="accent-jl-teal" @click.stop="toggleOption(o)" />
            {{ o.label }}
          </li>
          <li v-if="!filtered.length" class="px-3 py-2 text-slate-400">No options</li>
        </template>
      </ul>
    </div>
  </div>
</template>
