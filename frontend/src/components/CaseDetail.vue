<template>
  <div>
    <v-row>
      <v-col v-for="field in fields" :key="field.label" cols="12" md="6">
        <div class="mb-4">
          <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
            {{ field.label }}
          </v-list-item-subtitle>
          <v-chip v-if="field.chip" size="small" variant="tonal">{{ field.value }}</v-chip>
          <v-list-item-title v-else class="text-body-large text-wrap">
            {{ field.value }}
          </v-list-item-title>
        </div>
      </v-col>
      <v-col cols="12">
        <div class="mb-4">
          <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
            Assigned Users
          </v-list-item-subtitle>
          <div v-if="caseData?.users?.length" class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="user in caseData.users"
              :key="user.id"
              size="small"
              :variant="user.is_lead ? 'outlined' : 'tonal'"
            >
              <v-icon v-if="user.is_lead" size="x-small" start>mdi-star</v-icon>
              {{ user.username }}{{ user.is_lead ? ' · Lead' : '' }}
            </v-chip>
          </div>
          <v-list-item-title v-else class="text-body-large text-medium-emphasis">
            No users assigned
          </v-list-item-title>
        </div>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatDate } from '../composables/dateUtils'

const props = defineProps({
  caseData: { type: Object, required: true },
  client: { type: Object, default: () => ({}) },
})

const fields = computed(() => [
  { label: 'Title', value: props.caseData.title || 'N/A' },
  { label: 'Status', value: props.caseData.status || 'N/A', chip: true },
  { label: 'Client', value: props.client?.name || 'No client assigned' },
  { label: 'Created Date', value: formatDate(props.caseData.created_at) || 'N/A' },
])
</script>

<style scoped>
.text-body-large {
  overflow-wrap: anywhere;
}

:deep(.v-chip) {
  height: auto;
  min-height: 26px;
  max-width: 100%;
}

:deep(.v-chip__content) {
  white-space: normal;
  overflow-wrap: anywhere;
  min-width: 0;
}
</style>
