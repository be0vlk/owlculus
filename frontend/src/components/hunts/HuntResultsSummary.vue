<template>
  <div class="hunt-results-summary">
    <!-- Summary Stats -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card variant="tonal" color="success">
          <v-card-text class="text-center pa-3">
            <div class="text-h4 font-weight-bold">{{ completedSteps }}</div>
            <div class="text-caption">Completed Steps</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="tonal" color="error">
          <v-card-text class="text-center pa-3">
            <div class="text-h4 font-weight-bold">{{ failedSteps }}</div>
            <div class="text-caption">Failed Steps</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="tonal" color="primary">
          <v-card-text class="text-center pa-3">
            <div class="text-h4 font-weight-bold">{{ totalResults }}</div>
            <div class="text-caption">Total Results</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card variant="tonal" color="info">
          <v-card-text class="text-center pa-3">
            <div class="text-h4 font-weight-bold">{{ evidenceCount }}</div>
            <div class="text-caption">Evidence Created</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Evidence References -->
    <div v-if="evidenceRefs.length > 0" class="mb-4">
      <div class="text-h6 mb-3">Created Evidence</div>
      <v-list density="compact">
        <v-list-item
          v-for="evidenceRef in evidenceRefs"
          :key="evidenceRef"
          prepend-icon="mdi-file-document"
        >
          <v-list-item-title>Evidence #{{ evidenceRef }}</v-list-item-title>
          <v-list-item-subtitle>Hunt execution result</v-list-item-subtitle>
          <template #append>
            <v-btn
              icon="mdi-open-in-new"
              size="small"
              variant="text"
              @click="viewEvidence(evidenceRef)"
            />
          </template>
        </v-list-item>
      </v-list>
    </div>

    <!-- Context Metadata -->
    <div v-if="contextMetadata && Object.keys(contextMetadata).length > 0" class="mb-4">
      <div class="text-h6 mb-3">Hunt Metadata</div>
      <v-table density="compact">
        <tbody>
          <tr v-for="(value, key) in contextMetadata" :key="key">
            <td class="font-weight-medium">{{ formatMetadataKey(key) }}</td>
            <td>{{ formatMetadataValue(value) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>

    <!-- Empty State -->
    <div v-if="stepResults.length === 0" class="text-center pa-8">
      <v-icon icon="mdi-information" size="64" color="grey" class="mb-4" />
      <div class="text-h6 mb-2">No Results Available</div>
      <div class="text-body-2 text-medium-emphasis">
        This hunt execution did not generate any detailed results.
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatMetadataValue } from '@/utils/huntDisplayUtils'

const props = defineProps({
  execution: {
    type: Object,
    required: true,
  },
  contextData: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['view-evidence'])

// Computed properties
const stepResults = computed(() => {
  return props.execution.steps || []
})

const completedSteps = computed(() => {
  return stepResults.value.filter((step) => step.status === 'completed').length
})

const failedSteps = computed(() => {
  return stepResults.value.filter((step) => step.status === 'failed').length
})

const totalResults = computed(() => {
  return stepResults.value.reduce((total, step) => {
    const count = step.output?.result_count || step.output?.results?.length || 0
    return total + count
  }, 0)
})

const evidenceRefs = computed(() => {
  return props.contextData?.evidence_refs || []
})

const evidenceCount = computed(() => {
  return evidenceRefs.value.length
})

const contextMetadata = computed(() => {
  const metadata = props.contextData?.metadata || {}
  // Filter out internal keys
  const filtered = {}
  Object.keys(metadata).forEach((key) => {
    if (!key.startsWith('_') && key !== 'evidence_refs' && key !== 'step_outputs') {
      filtered[key] = metadata[key]
    }
  })
  return filtered
})

// Methods
const formatMetadataKey = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

const viewEvidence = (evidenceRef) => {
  emit('view-evidence', evidenceRef)
}
</script>

<style scoped>
.v-table tbody td {
  padding: 8px 12px;
}
</style>
