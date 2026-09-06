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
      <p class="active-case-label">Active case</p>
      <v-select
        :model-value="activeCase.activeCaseId"
        :items="options"
        :aria-label="`Active case: ${activeCase.activeCase?.case_number} — ${activeCase.activeCase?.title}. Switch case`"
        item-title="label"
        item-value="id"
        :clearable="false"
        :disabled="!activeCase.ready || activeCase.refreshing"
        :loading="activeCase.refreshing"
        hide-details
        density="compact"
        variant="solo-filled"
        flat
        rounded="lg"
        class="active-case-select"
        :menu-props="{ maxHeight: 360, width: 360, maxWidth: 'calc(100vw - 32px)' }"
        :list-props="{ 'aria-label': 'Cases', 'aria-labelledby': undefined }"
        @update:model-value="activeCase.select($event)"
      >
        <template #selection="{ item }">
          <div class="active-case-summary" :title="item.title">
            <div class="active-case-meta">
              <span class="active-case-number">{{ item.case_number }}</span>
              <v-chip
                :color="item.status === 'Open' ? 'success' : undefined"
                size="x-small"
                variant="tonal"
              >
                {{ item.status }}
              </v-chip>
            </div>
            <span class="active-case-title">{{ item.title }}</span>
          </div>
        </template>
        <template #item="{ props, item }">
          <v-list-item v-bind="props" class="active-case-option" :title="item.case_number">
            <template #subtitle>
              <span class="active-case-option-title">{{ item.title }}</span>
            </template>
            <template #append>
              <v-chip
                :color="item.status === 'Open' ? 'success' : undefined"
                size="x-small"
                variant="tonal"
              >
                {{ item.status }}
              </v-chip>
            </template>
          </v-list-item>
        </template>
      </v-select>
      <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        Active case: {{ activeCase.activeCase?.case_number }} — {{ activeCase.activeCase?.title }} ·
        {{ activeCase.activeCase?.status }}
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
    ...item,
    label: `${item.case_number} — ${item.title} (${item.status})`,
  })),
)
</script>

<style scoped>
.active-case-switcher {
  width: 100%;
  min-width: 0;
}

.active-case-label {
  margin: 0 0 6px;
  color: rgb(var(--v-theme-on-surface), 0.65);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.active-case-select :deep(.v-field) {
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
}

.active-case-select :deep(.v-field--focused) {
  outline: 2px solid rgb(var(--v-theme-on-surface), 0.65);
  outline-offset: 2px;
}

.active-case-select :deep(.v-select__selection) {
  width: 100%;
  max-width: 100%;
}

.active-case-summary {
  width: 100%;
  min-width: 0;
  padding-block: 2px;
}

.active-case-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.active-case-number {
  font-size: 0.8125rem;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.active-case-title {
  display: block;
  overflow: hidden;
  font-size: 0.8125rem;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-case-option {
  padding-block: 8px;
}

.active-case-option :deep(.v-list-item-subtitle) {
  display: block;
  margin-top: 4px;
  opacity: 0.8;
}

.active-case-option-title {
  white-space: normal;
  overflow-wrap: anywhere;
}

.active-case-option :deep(.v-list-item__append) {
  padding-inline-start: 12px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
