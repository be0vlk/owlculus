<template>
  <div class="hunt-step-results">
    <div class="mb-4">
      <v-row>
        <v-col cols="12" md="6">
          <div class="text-body-small font-weight-medium">Plugin</div>
          <div class="text-body-medium">{{ step.plugin_name }}</div>
        </v-col>
        <v-col cols="12" md="6">
          <div class="text-body-small font-weight-medium">Step ID</div>
          <div class="text-body-medium">{{ step.step_id }}</div>
        </v-col>
      </v-row>

      <div v-if="step.parameters && Object.keys(step.parameters).length > 0" class="mt-3">
        <div class="text-body-small font-weight-medium mb-2">Parameters</div>
        <v-chip
          v-for="(value, key) in step.parameters"
          :key="key"
          size="small"
          variant="outlined"
          class="mr-2 mb-1"
        >
          {{ key }}: {{ value }}
        </v-chip>
      </div>

      <div
        v-if="
          step.plugin_name !== 'CorrelationScan' && step.status === 'failed' && step.error_details
        "
        class="mt-3"
      >
        <v-alert type="error" variant="tonal" density="compact">
          {{ step.error_details }}
        </v-alert>
      </div>
    </div>

    <v-divider class="mb-4" />

    <v-alert
      v-if="
        step.plugin_name !== 'CorrelationScan' &&
        displayResults.length &&
        (step.status !== 'completed' || step.output?.partial || step.output?.errors?.length)
      "
      type="warning"
      role="alert"
      class="mb-4"
    >
      Partial retained results. This step has not completed successfully.
    </v-alert>
    <template v-if="step.plugin_name === 'CorrelationScan'">
      <p role="status">Step {{ step.status }}.</p>
      <PluginResult
        plugin-name="CorrelationScan"
        :result="correlationEvents"
        :execution-status="step.status"
        :execution-partial="!!step.output?.partial"
        :execution-error="correlationExecutionError"
        :retrieval-loading="retrievalLoading"
        :retrieval-complete="!retrievalLoading && !retrievalError"
        :retrieval-error="retrievalError"
        :export-error="exportError"
        @retry="$emit('retry')"
      />
    </template>
    <div v-else-if="displayResults.length > 0">
      <div v-for="(result, index) in displayResults" :key="index" class="result-item mb-3">
        <v-card variant="outlined" density="compact">
          <v-card-text class="pa-3">
            <div v-if="typeof result === 'object'">
              <div v-for="(value, key) in result" :key="key" class="mb-1">
                <span class="text-body-small font-weight-medium"
                  >{{ formatParameterName(key) }}:</span
                >
                <span class="text-body-small ml-2">{{ formatValue(value) }}</span>
              </div>
            </div>
            <div v-else class="text-body-medium">
              {{ result }}
            </div>
          </v-card-text>
        </v-card>
      </div>
    </div>

    <div v-else-if="step.status === 'completed'" class="text-center pa-4">
      <v-icon icon="mdi-information-outline" color="grey" class="mb-2" />
      <div class="text-body-small text-medium-emphasis">No results to display</div>
    </div>

    <div v-else-if="step.status === 'pending'" class="text-center pa-4">
      <v-icon icon="mdi-clock-outline" color="grey" class="mb-2" />
      <div class="text-body-small text-medium-emphasis">Step not yet executed</div>
    </div>

    <div v-else-if="step.status === 'running'" class="text-center pa-4">
      <v-progress-circular indeterminate size="32" color="primary" />
      <div class="text-body-small text-medium-emphasis mt-2">Step is currently running...</div>
    </div>

    <div v-else-if="step.status === 'skipped'" class="text-center pa-4">
      <v-icon icon="mdi-skip-next" color="warning" class="mb-2" />
      <div class="text-body-small text-medium-emphasis">Step was skipped</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import PluginResult from '@/components/plugins/PluginResult.vue'
import { huntCorrelationEvents } from '@/utils/huntResults'
import { formatParameterName } from '@/utils/huntDisplayUtils'

defineEmits(['retry'])
const props = defineProps({
  exportError: { type: String, default: null },
  retrievalLoading: { type: Boolean, default: false },
  retrievalError: { type: String, default: null },
  step: {
    type: Object,
    required: true,
  },
})

const correlationEvents = computed(() => huntCorrelationEvents(props.step))
const correlationExecutionError = computed(() =>
  correlationEvents.value.some(
    (event) => event.type === 'error' && event.data?.message === props.step.error_details,
  )
    ? null
    : props.step.error_details,
)

const displayResults = computed(() => {
  if (!props.step?.output) return []

  if (Array.isArray(props.step.output)) {
    return props.step.output
  } else if (props.step.output.results && Array.isArray(props.step.output.results)) {
    return props.step.output.results
  } else if (props.step.output.data && Array.isArray(props.step.output.data)) {
    return props.step.output.data
  } else if (typeof props.step.output === 'object') {
    return [props.step.output]
  }
  return []
})

const formatValue = (value) => {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && value.length > 100) {
    return value.substring(0, 97) + '...'
  }
  return String(value)
}
</script>

<style scoped>
.result-item {
  transition: all 0.2s ease;
}

.result-item:hover {
  transform: translateY(-1px);
}
</style>
