<template>
  <v-card class="hunt-progress-card" elevation="2" rounded="lg">
    <!-- Header -->
    <v-card-title class="d-flex align-center pa-4 text-no-wrap">
      <v-avatar :color="statusColor" size="40" class="me-3">
        <v-icon :icon="statusIcon" color="white" />
      </v-avatar>
      <div class="flex-grow-1 text-truncate">
        <div class="text-h6 font-weight-bold text-truncate">{{ huntDisplayTitle }}</div>
        <div class="text-caption text-medium-emphasis text-truncate">
          Execution #{{ execution.id }}
          <span v-if="execution.hunt">• {{ execution.hunt.category }}</span>
        </div>
      </div>
      <v-chip :color="statusColor" variant="flat" size="small">
        {{ statusText }}
      </v-chip>
    </v-card-title>

    <v-divider />

    <!-- Progress Section -->
    <v-card-text class="pa-4">
      <!-- Timing Information -->
      <div class="timing-info mb-4">
        <div class="d-flex align-center flex-wrap">
          <div class="d-flex align-center me-4 mb-1">
            <v-icon icon="mdi-clock-start" size="small" class="me-1" />
            <span class="text-caption">Started: {{ formatDate(execution.started_at) }}</span>
          </div>
          <div v-if="execution.completed_at" class="d-flex align-center mb-1">
            <v-icon icon="mdi-clock-end" size="small" class="me-1" />
            <span class="text-caption">Completed: {{ formatDate(execution.completed_at) }}</span>
          </div>
          <div v-else-if="execution.status === 'running'" class="d-flex align-center mb-1">
            <v-icon icon="mdi-clock" size="small" class="me-1" />
            <span class="text-caption">{{ elapsedTime }}</span>
          </div>
        </div>
      </div>

      <!-- Step Progress -->
      <div v-if="execution.steps && execution.steps.length > 0" class="mb-4">
        <div class="text-body-2 font-weight-medium mb-3">Hunt Steps</div>
        <div class="step-list">
          <div
            v-for="(step, index) in execution.steps"
            :key="step.id"
            class="step-item d-flex align-center mb-2"
          >
            <!-- Step Status Icon -->
            <v-avatar :color="getStepStatusColor(step.status)" size="24" class="me-3">
              <v-icon :icon="getStepStatusIcon(step.status)" color="white" size="small" />
            </v-avatar>

            <!-- Step Info -->
            <div class="flex-grow-1 text-truncate">
              <div class="text-body-2 text-truncate">{{ step.step_id || `Step ${index + 1}` }}</div>
              <div class="text-caption text-medium-emphasis text-truncate">
                {{ step.plugin_name }}
              </div>
            </div>

            <!-- Step Status -->
            <v-chip :color="getStepStatusColor(step.status)" variant="flat" size="x-small">
              {{ step.status }}
            </v-chip>
          </div>
        </div>
      </div>

      <!-- Error Display -->
      <v-alert
        v-if="execution.status === 'failed' || hasFailedSteps"
        type="error"
        variant="tonal"
        class="mb-4"
      >
        <div class="text-body-2 font-weight-medium mb-1">
          {{ execution.status === 'failed' ? 'Hunt Failed' : 'Some Steps Failed' }}
        </div>
        <div v-if="failedSteps.length > 0" class="text-caption">
          Failed steps: {{ failedSteps.map((s) => s.step_id).join(', ') }}
        </div>
      </v-alert>

      <!-- Results Summary -->
      <div v-if="execution.status === 'completed' || execution.status === 'partial'" class="mb-4">
        <div class="text-body-2 font-weight-medium mb-2">Results Summary</div>
        <div class="d-flex align-center flex-wrap">
          <div class="d-flex align-center me-4 mb-1">
            <v-icon icon="mdi-check-circle" color="success" size="small" class="me-1" />
            <span class="text-caption">{{ completedSteps.length }} steps completed</span>
          </div>
          <div v-if="failedSteps.length > 0" class="d-flex align-center mb-1">
            <v-icon icon="mdi-alert-circle" color="error" size="small" class="me-1" />
            <span class="text-caption">{{ failedSteps.length }} steps failed</span>
          </div>
        </div>
      </div>
    </v-card-text>

    <!-- Actions -->
    <v-card-actions class="pa-4 pt-0 flex-wrap">
      <v-btn
        v-if="execution.status === 'running'"
        color="error"
        variant="outlined"
        size="small"
        @click="$emit('cancel', execution.id)"
        :loading="cancelling"
        class="mb-2 mb-sm-0"
      >
        <v-icon icon="mdi-stop" start />
        Cancel
      </v-btn>

      <v-spacer class="d-none d-sm-flex" />

      <v-btn
        color="primary"
        :variant="
          execution.status === 'completed' || execution.status === 'partial' ? 'elevated' : 'text'
        "
        size="small"
        @click="$emit('view-details', execution.id)"
        class="mb-2 mb-sm-0"
      >
        <v-icon
          :icon="
            execution.status === 'completed' || execution.status === 'partial'
              ? 'mdi-eye'
              : 'mdi-information'
          "
          start
        />
        <span class="d-none d-sm-inline">{{
          execution.status === 'completed' || execution.status === 'partial'
            ? 'View Results'
            : 'View Details'
        }}</span>
        <span class="d-inline d-sm-none">{{
          execution.status === 'completed' || execution.status === 'partial' ? 'Results' : 'Details'
        }}</span>
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { formatHuntExecutionTitle } from '@/utils/huntDisplayUtils'
import { formatDate } from '@/composables/dateUtils'

const props = defineProps({
  execution: {
    type: Object,
    required: true,
  },
  cancelling: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['cancel', 'view-details'])

// Local state
const elapsedTime = ref('')
let elapsedInterval = null

// Computed properties
const statusColor = computed(() => {
  switch (props.execution.status) {
    case 'pending':
      return 'grey'
    case 'running':
      return 'primary'
    case 'completed':
      return 'success'
    case 'partial':
      return 'warning'
    case 'failed':
      return 'error'
    case 'cancelled':
      return 'grey'
    default:
      return 'grey'
  }
})

const statusIcon = computed(() => {
  switch (props.execution.status) {
    case 'pending':
      return 'mdi-clock-outline'
    case 'running':
      return 'mdi-play'
    case 'completed':
      return 'mdi-check'
    case 'partial':
      return 'mdi-alert'
    case 'failed':
      return 'mdi-close'
    case 'cancelled':
      return 'mdi-stop'
    default:
      return 'mdi-help'
  }
})

const statusText = computed(() => {
  switch (props.execution.status) {
    case 'pending':
      return 'Pending'
    case 'running':
      return 'Running'
    case 'completed':
      return 'Completed'
    case 'partial':
      return 'Partial'
    case 'failed':
      return 'Failed'
    case 'cancelled':
      return 'Cancelled'
    default:
      return 'Unknown'
  }
})

const completedSteps = computed(() => {
  if (!props.execution.steps) return []
  return props.execution.steps.filter((step) => step.status === 'completed')
})

const failedSteps = computed(() => {
  if (!props.execution.steps) return []
  return props.execution.steps.filter((step) => step.status === 'failed')
})

const hasFailedSteps = computed(() => {
  return failedSteps.value.length > 0
})

const huntDisplayTitle = computed(() => {
  const baseName = props.execution.hunt?.display_name || 'Hunt Execution'
  const initialParams = props.execution.initial_parameters || {}
  const huntCategory = props.execution.hunt?.category || 'general'

  return formatHuntExecutionTitle(baseName, initialParams, huntCategory)
})

// Methods
const getStepStatusColor = (status) => {
  switch (status) {
    case 'pending':
      return 'grey'
    case 'running':
      return 'primary'
    case 'completed':
      return 'success'
    case 'failed':
      return 'error'
    case 'skipped':
      return 'warning'
    case 'cancelled':
      return 'grey'
    default:
      return 'grey'
  }
}

const getStepStatusIcon = (status) => {
  switch (status) {
    case 'pending':
      return 'mdi-clock-outline'
    case 'running':
      return 'mdi-play'
    case 'completed':
      return 'mdi-check'
    case 'failed':
      return 'mdi-close'
    case 'skipped':
      return 'mdi-skip-next'
    case 'cancelled':
      return 'mdi-stop'
    default:
      return 'mdi-help'
  }
}

// formatDate is now imported from dateUtils

const updateElapsedTime = () => {
  if (props.execution.status !== 'running' || !props.execution.started_at) {
    elapsedTime.value = ''
    return
  }

  // Ensure the timestamp is parsed as UTC by appending 'Z' if it doesn't have timezone info
  let startTimeStr = props.execution.started_at
  if (
    !startTimeStr.includes('Z') &&
    !startTimeStr.includes('+') &&
    !startTimeStr.includes('-', 10)
  ) {
    startTimeStr += 'Z'
  }

  const startTime = new Date(startTimeStr)
  const now = new Date()
  const diff = now - startTime

  // Ensure we don't show negative times
  if (diff < 0) {
    elapsedTime.value = '0s'
    return
  }

  const minutes = Math.floor(diff / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)

  if (minutes > 0) {
    elapsedTime.value = `${minutes}m ${seconds}s`
  } else {
    elapsedTime.value = `${seconds}s`
  }
}

// Lifecycle
onMounted(() => {
  updateElapsedTime()
  if (props.execution.status === 'running') {
    elapsedInterval = setInterval(updateElapsedTime, 1000)
  }
})

onUnmounted(() => {
  if (elapsedInterval) {
    clearInterval(elapsedInterval)
  }
})

// Watch for status changes
import { watch } from 'vue'
watch(
  () => props.execution.status,
  (newStatus) => {
    if (newStatus === 'running' && !elapsedInterval) {
      updateElapsedTime()
      elapsedInterval = setInterval(updateElapsedTime, 1000)
    } else if (newStatus !== 'running' && elapsedInterval) {
      clearInterval(elapsedInterval)
      elapsedInterval = null
      elapsedTime.value = ''
    }
  },
)
</script>

<style scoped>
.hunt-progress-card {
  min-height: 300px;
  width: 100%;
  overflow: hidden;
}

.step-list {
  max-height: 200px;
  overflow-y: auto;
  overflow-x: hidden;
}

.step-item {
  border-radius: 8px;
  padding: 8px;
  transition: background-color 0.2s ease;
  min-width: 0; /* Enable text truncation in flexbox */
}

.step-item:hover {
  background-color: rgba(var(--v-theme-surface-variant), 0.1);
}

/* Ensure proper text truncation */
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive adjustments */
@media (max-width: 600px) {
  .hunt-progress-card {
    min-height: 280px;
  }

  .hunt-progress-card .v-card-title {
    padding: 12px !important;
  }

  .hunt-progress-card .v-card-text {
    padding: 12px !important;
  }

  .hunt-progress-card .v-card-actions {
    padding: 12px !important;
    padding-top: 0 !important;
  }
}

/* Prevent overflow on timing information */
.timing-info {
  overflow: hidden;
}
</style>
