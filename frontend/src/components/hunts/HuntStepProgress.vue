<template>
  <div class="hunt-step-progress" :class="{ 'step-last': isLast }">
    <div class="d-flex align-center pa-4">
      <!-- Step Number and Status -->
      <div class="step-indicator me-4">
        <v-avatar :color="statusColor" size="40">
          <v-icon :icon="statusIcon" color="white" size="small" />
        </v-avatar>
        <div v-if="!isLast" class="step-connector" :class="stepConnectorClass" />
      </div>

      <!-- Step Content -->
      <div class="flex-grow-1">
        <div class="d-flex align-center justify-space-between mb-2">
          <div>
            <div class="text-h6 font-weight-medium">
              Step {{ stepNumber }}: {{ step.step_id }}
            </div>
            <div class="text-body-2 text-medium-emphasis">
              {{ step.plugin_name }}
            </div>
          </div>
          <v-chip :color="statusColor" variant="flat" size="small">
            {{ statusText }}
          </v-chip>
        </div>

        <!-- Timing Information -->
        <div class="d-flex align-center mb-2">
          <div v-if="step.started_at" class="me-4">
            <v-icon icon="mdi-clock-start" size="small" class="me-1" />
            <span class="text-caption">Started: {{ formatTimeOnly(step.started_at) }}</span>
          </div>
          <div v-if="step.completed_at" class="me-4">
            <v-icon icon="mdi-clock-end" size="small" class="me-1" />
            <span class="text-caption">Completed: {{ formatTimeOnly(step.completed_at) }}</span>
          </div>
          <div v-if="duration" class="me-4">
            <v-icon icon="mdi-timer" size="small" class="me-1" />
            <span class="text-caption">Duration: {{ duration }}</span>
          </div>
          <div v-if="step.retry_count > 0">
            <v-icon icon="mdi-refresh" size="small" class="me-1" />
            <span class="text-caption">Retries: {{ step.retry_count }}</span>
          </div>
        </div>

        <!-- Parameters -->
        <div v-if="step.parameters && Object.keys(step.parameters).length > 0" class="mb-2">
          <v-expansion-panels variant="accordion" class="step-parameters">
            <v-expansion-panel>
              <v-expansion-panel-title class="text-caption">
                <v-icon icon="mdi-cog" size="small" class="me-2" />
                Step Parameters
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-table density="compact">
                  <tbody>
                    <tr v-for="(value, key) in step.parameters" :key="key">
                      <td class="text-caption font-weight-medium">{{ key }}</td>
                      <td class="text-caption">{{ formatParameterValue(value) }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>

        <!-- Step Actions -->
        <div class="d-flex align-center ga-2">
          <v-btn
            v-if="step.output"
            size="small"
            variant="outlined"
            prepend-icon="mdi-eye"
            @click="$emit('view-output', step)"
          >
            View Output
          </v-btn>
          <v-btn
            v-if="step.error_details"
            size="small"
            variant="outlined"
            color="error"
            prepend-icon="mdi-alert"
            @click="$emit('view-error', step)"
          >
            View Error
          </v-btn>
        </div>

        <!-- Error Summary -->
        <v-alert
          v-if="step.status === 'failed' && step.error_details"
          type="error"
          variant="tonal"
          class="mt-3"
          density="compact"
        >
          <div class="text-caption font-weight-medium">Step Failed</div>
          <div class="text-caption">{{ truncateError(step.error_details) }}</div>
          <v-btn
            v-if="step.error_details.length > 100"
            size="x-small"
            variant="text"
            color="error"
            @click="$emit('view-error', step)"
            class="mt-1"
          >
            View Full Error
          </v-btn>
        </v-alert>

        <!-- Output Summary -->
        <v-alert
          v-if="step.status === 'completed' && step.output"
          type="success"
          variant="tonal"
          class="mt-3"
          density="compact"
        >
          <div class="text-caption font-weight-medium">Step Completed</div>
          <div class="text-caption">
            {{ getOutputSummary(step.output) }}
          </div>
        </v-alert>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatTimeOnly } from '@/composables/dateUtils'

const props = defineProps({
  step: {
    type: Object,
    required: true
  },
  stepNumber: {
    type: Number,
    required: true
  },
  isLast: {
    type: Boolean,
    default: false
  }
})

defineEmits(['view-output', 'view-error'])

// Computed properties
const statusColor = computed(() => {
  switch (props.step.status) {
    case 'pending': return 'grey'
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'failed': return 'error'
    case 'skipped': return 'warning'
    case 'cancelled': return 'grey'
    default: return 'grey'
  }
})

const statusIcon = computed(() => {
  switch (props.step.status) {
    case 'pending': return 'mdi-clock-outline'
    case 'running': return 'mdi-play'
    case 'completed': return 'mdi-check'
    case 'failed': return 'mdi-close'
    case 'skipped': return 'mdi-skip-next'
    case 'cancelled': return 'mdi-stop'
    default: return 'mdi-help'
  }
})

const statusText = computed(() => {
  switch (props.step.status) {
    case 'pending': return 'Pending'
    case 'running': return 'Running'
    case 'completed': return 'Completed'
    case 'failed': return 'Failed'
    case 'skipped': return 'Skipped'
    case 'cancelled': return 'Cancelled'
    default: return 'Unknown'
  }
})

const stepConnectorClass = computed(() => {
  // Color the connector based on the current step status
  return `connector-${statusColor.value}`
})

const duration = computed(() => {
  if (!props.step.started_at || !props.step.completed_at) return null
  
  const startTime = new Date(props.step.started_at)
  const endTime = new Date(props.step.completed_at)
  const diffMs = endTime - startTime
  
  if (diffMs < 1000) return '< 1s'
  
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  
  if (diffMinutes > 0) {
    return `${diffMinutes}m ${diffSeconds % 60}s`
  } else {
    return `${diffSeconds}s`
  }
})

// Methods

const formatParameterValue = (value) => {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && value.length > 50) {
    return value.substring(0, 47) + '...'
  }
  return String(value)
}

const truncateError = (error) => {
  if (!error) return ''
  return error.length > 100 ? error.substring(0, 97) + '...' : error
}

const getOutputSummary = (output) => {
  if (!output) return 'No output data'
  
  if (output.result_count !== undefined) {
    return `Generated ${output.result_count} result(s)`
  }
  
  if (output.results && Array.isArray(output.results)) {
    return `Generated ${output.results.length} result(s)`
  }
  
  if (typeof output === 'object') {
    const keys = Object.keys(output)
    return `Output contains: ${keys.slice(0, 3).join(', ')}${keys.length > 3 ? '...' : ''}`
  }
  
  return 'Step completed successfully'
}
</script>

<style scoped>
.hunt-step-progress {
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
}

.hunt-step-progress.step-last {
  border-bottom: none;
}

.step-indicator {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.step-connector {
  width: 2px;
  height: 60px;
  margin-top: 8px;
  background-color: rgba(var(--v-theme-outline), 0.3);
  border-radius: 1px;
}

.step-connector.connector-success {
  background-color: rgb(var(--v-theme-success));
}

.step-connector.connector-error {
  background-color: rgb(var(--v-theme-error));
}

.step-connector.connector-primary {
  background-color: rgb(var(--v-theme-primary));
}

.step-connector.connector-warning {
  background-color: rgb(var(--v-theme-warning));
}

.step-parameters {
  max-width: 500px;
}

.step-parameters :deep(.v-expansion-panel-title) {
  min-height: 36px !important;
  padding: 8px 16px !important;
}

.step-parameters :deep(.v-expansion-panel-text__wrapper) {
  padding: 8px 16px !important;
}

.step-parameters .v-table {
  background-color: transparent;
}

.step-parameters .v-table td {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
}
</style>