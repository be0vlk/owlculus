<template>
  <div class="active-case-switcher pa-3">
    <p v-if="activeCase.loading || (!activeCase.initialized && !activeCase.error)" role="status">
      Loading cases…
    </p>
    <div v-else-if="activeCase.error" role="alert">
      <p>{{ activeCase.error }}</p>
      <v-btn size="small" @click="activeCase.refresh()">Retry loading cases</v-btn>
    </div>
    <template v-else-if="activeCase.accessibleCases.length">
      <v-autocomplete
        :model-value="activeCase.activeCaseId"
        :items="options"
        label="Active case"
        item-title="label"
        item-value="id"
        :clearable="false"
        :disabled="!activeCase.ready || activeCase.refreshing"
        :loading="activeCase.refreshing"
        auto-select-first
        hide-details
        density="compact"
        variant="outlined"
        @update:model-value="activeCase.select($event)"
      />
      <p class="text-body-small mt-2" role="status" aria-live="polite" aria-atomic="true">
        Active case: {{ activeCase.activeCase?.case_number }} · {{ activeCase.activeCase?.status }}
      </p>
    </template>
    <div v-else role="status">
      <p>No accessible cases</p>
      <p v-if="!auth.requiresAdmin()" class="text-body-small">
        Contact an administrator to be assigned to a case.
      </p>
      <v-btn v-else to="/cases?create=1" size="small" variant="text">Create a case</v-btn>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useActiveCaseStore } from '../stores/activeCase'
import { useAuthStore } from '../stores/auth'

const activeCase = useActiveCaseStore()
const auth = useAuthStore()
const options = computed(() =>
  activeCase.accessibleCases.map((item) => ({
    id: item.id,
    label: `${item.case_number} — ${item.title} (${item.status})`,
  })),
)
</script>

<style scoped>
.active-case-switcher {
  width: 100%;
  min-width: 0;
}
</style>
