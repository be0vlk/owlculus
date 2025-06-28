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

    <!-- Step Results Overview -->
    <div v-if="stepResults.length > 0" class="mb-4">
      <div class="text-h6 mb-3">Step Results Overview</div>
      <v-expansion-panels variant="accordion">
        <v-expansion-panel
          v-for="stepResult in stepResults"
          :key="stepResult.step_id"
        >
          <v-expansion-panel-title>
            <div class="d-flex align-center">
              <v-avatar :color="getStatusColor(stepResult.status)" size="24" class="me-3">
                <v-icon :icon="getStatusIcon(stepResult.status)" color="white" size="x-small" />
              </v-avatar>
              <div class="flex-grow-1">
                <div class="text-body-1 font-weight-medium">{{ stepResult.step_id }}</div>
                <div class="text-caption text-medium-emphasis">{{ stepResult.plugin_name }}</div>
              </div>
              <v-chip :color="getStatusColor(stepResult.status)" variant="flat" size="small" class="me-2">
                {{ stepResult.status }}
              </v-chip>
              <div v-if="stepResult.result_count !== undefined" class="text-caption">
                {{ stepResult.result_count }} results
              </div>
            </div>
          </v-expansion-panel-title>

          <v-expansion-panel-text>
            <!-- Step Results -->
            <div v-if="stepResult.status === 'completed' && stepResult.output">
              <div class="mb-3">
                <div class="text-body-2 font-weight-medium mb-2">Results</div>
                <div v-if="stepResult.output.results && stepResult.output.results.length > 0">
                  <HuntStepResults
                    :plugin-name="stepResult.plugin_name"
                    :results="stepResult.output.results"
                    :max-display="3"
                  />
                  <v-btn
                    v-if="stepResult.output.results.length > 3"
                    size="small"
                    variant="text"
                    color="primary"
                    @click="viewFullStepResults(stepResult)"
                    class="mt-2"
                  >
                    View All {{ stepResult.output.results.length }} Results
                  </v-btn>
                </div>
                <div v-else class="text-body-2 text-medium-emphasis">
                  No detailed results available
                </div>
              </div>
            </div>

            <!-- Step Error -->
            <div v-else-if="stepResult.status === 'failed' && stepResult.error_details">
              <v-alert type="error" variant="tonal" density="compact">
                <div class="text-body-2 font-weight-medium">Error Details</div>
                <div class="text-caption mt-1">{{ stepResult.error_details }}</div>
              </v-alert>
            </div>

            <!-- Step Skipped -->
            <div v-else-if="stepResult.status === 'skipped'">
              <v-alert type="info" variant="tonal" density="compact">
                This step was skipped due to failed dependencies or optional configuration.
              </v-alert>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </div>

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
import { getStatusColor, getStatusIcon, formatMetadataValue } from '@/utils/huntDisplayUtils'
import HuntStepResults from './HuntStepResults.vue'

const props = defineProps({
  execution: {
    type: Object,
    required: true
  },
  contextData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['view-step-results', 'view-evidence'])

// Computed properties
const stepResults = computed(() => {
  if (!props.execution.steps) return []
  
  return props.execution.steps.map(step => ({
    step_id: step.step_id,
    plugin_name: step.plugin_name,
    status: step.status,
    output: step.output,
    error_details: step.error_details,
    result_count: step.output?.result_count || step.output?.results?.length || 0
  }))
})

const completedSteps = computed(() => {
  return stepResults.value.filter(step => step.status === 'completed').length
})

const failedSteps = computed(() => {
  return stepResults.value.filter(step => step.status === 'failed').length
})

const totalResults = computed(() => {
  return stepResults.value.reduce((total, step) => {
    return total + (step.result_count || 0)
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
  Object.keys(metadata).forEach(key => {
    if (!key.startsWith('_') && key !== 'evidence_refs' && key !== 'step_outputs') {
      filtered[key] = metadata[key]
    }
  })
  return filtered
})

// Methods
const formatMetadataKey = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const viewFullStepResults = (stepResult) => {
  emit('view-step-results', stepResult)
}

const viewEvidence = (evidenceRef) => {
  emit('view-evidence', evidenceRef)
}
</script>

<style scoped>
.hunt-results-summary .v-expansion-panel-title {
  padding: 12px 16px;
}

.v-table tbody td {
  padding: 8px 12px;
}
</style>