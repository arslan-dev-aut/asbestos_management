<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TypeListPanel from './TypeListPanel.vue'
import ConfigAuditPanel from './ConfigAuditPanel.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import * as svc from '@/services/configuration.service'
import { notify } from '@/utils/notify'
import type { BuildingType, AcmType, ConfigAuditEntry } from '@/types'

type SubTab = 'building' | 'acm' | 'audit'
const subTab = ref<SubTab>('building')

const buildingTypes = ref<BuildingType[]>([])
const acmTypes = ref<AcmType[]>([])
const audit = ref<ConfigAuditEntry[]>([])
const loading = ref(true)

async function loadAll() {
  loading.value = true
  try {
    ;[buildingTypes.value, acmTypes.value, audit.value] = await Promise.all([
      svc.getBuildingTypes(),
      svc.getAcmTypes(),
      svc.getConfigAudit(),
    ])
  } finally {
    loading.value = false
  }
}
onMounted(loadAll)

async function addBuilding(name: string) {
  await svc.addBuildingType(name)
  ;[buildingTypes.value, audit.value] = await Promise.all([svc.getBuildingTypes(), svc.getConfigAudit()])
  notify.success(`Building type "${name}" added.`)
}
async function toggleBuilding(id: string, isActive: boolean) {
  await svc.toggleBuildingType(id, isActive)
  ;[buildingTypes.value, audit.value] = await Promise.all([svc.getBuildingTypes(), svc.getConfigAudit()])
  notify.success(isActive ? 'Building type activated.' : 'Building type deactivated.')
}
async function addAcm(name: string) {
  await svc.addAcmType(name)
  ;[acmTypes.value, audit.value] = await Promise.all([svc.getAcmTypes(), svc.getConfigAudit()])
  notify.success(`ACM type "${name}" added.`)
}
async function toggleAcm(id: string, isActive: boolean) {
  await svc.toggleAcmType(id, isActive)
  ;[acmTypes.value, audit.value] = await Promise.all([svc.getAcmTypes(), svc.getConfigAudit()])
  notify.success(isActive ? 'ACM type activated.' : 'ACM type deactivated.')
}

const tabs: { key: SubTab; label: string }[] = [
  { key: 'building', label: 'Building Types' },
  { key: 'acm', label: 'ACM Types' },
  { key: 'audit', label: 'Audit' },
]
</script>

<template>
  <div>
    <!-- Sub-tabs (pill style) -->
    <div class="mb-5 inline-flex gap-2 rounded-lg bg-white p-1 shadow-sm">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="rounded-md px-4 py-2 text-sm font-semibold transition"
        :class="subTab === t.key ? 'bg-jl-navy text-white' : 'text-slate-500 hover:text-jl-navy'"
        @click="subTab = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <LoadingState v-if="loading" message="Loading configuration…" />

    <TypeListPanel
      v-else-if="subTab === 'building'"
      :items="buildingTypes"
      placeholder="Add a new building type..."
      noun="building type"
      :on-add="addBuilding"
      :on-toggle="toggleBuilding"
    />
    <TypeListPanel
      v-else-if="subTab === 'acm'"
      :items="acmTypes"
      placeholder="Add a new ACM type..."
      noun="ACM type"
      :on-add="addAcm"
      :on-toggle="toggleAcm"
    />
    <ConfigAuditPanel v-else :entries="audit" />
  </div>
</template>
