<script setup lang="ts">
import { computed } from 'vue'
import type { RagColour, RiskScore } from '@/types'
import { riskToRag, ragBadgeClass } from '@/utils/rag'
import { riskLabel } from '@/utils/const'

const props = defineProps<{
  // Pass either a risk score (HIGH/MEDIUM/LOW/NONE) or a raw RAG colour + label
  risk?: RiskScore | 'NONE'
  rag?: RagColour
  label?: string
}>()

const rag = computed<RagColour>(() => props.rag ?? riskToRag(props.risk ?? 'NONE'))
const text = computed(() => props.label ?? (props.risk && props.risk !== 'NONE' ? riskLabel(props.risk).toUpperCase() : 'NONE'))
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide"
    :class="ragBadgeClass(rag)"
  >
    <!-- RED: triangle warning -->
    <svg v-if="rag === 'RED'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M10.3 3.2 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.2a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
    <!-- AMBER: pie / clock segment -->
    <svg v-else-if="rag === 'AMBER'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 12V5" />
      <path d="M12 12h6" />
    </svg>
    <!-- GREEN: circle with tick -->
    <svg v-else-if="rag === 'GREEN'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </svg>
    <!-- NONE: dash -->
    <span v-else aria-hidden="true">—</span>
    {{ text }}
  </span>
</template>
