<template>
  <v-card class="hunt-progress-card" elevation="1" rounded="lg">
    <!-- Header -->
    <v-card-title class="d-flex align-center pa-3 pa-sm-4 text-no-wrap">
      <v-avatar :color="statusColor" size="40" class="me-3">
        <v-icon :icon="statusIcon" color="white" />
      </v-avatar>
      <div class="flex-grow-1 text-truncate">
        <div class="text-title-large font-weight-bold text-truncate">{{ huntDisplayTitle }}</div>
        <div class="text-body-small text-medium-emphasis text-truncate">
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
    <v-card-text class="pa-3 pa-sm-4">
      <ExecutionWaiting :execution="execution" />
      <!-- Timing Information -->
      <div class="timing-info mb-4">
        <div class="d-flex align-center flex-wrap">
          <div class="d-flex align-center me-4 mb-1">
            <v-icon icon="mdi-clock-start" size="small" class="me-1" />
            <span class="text-body-small">Started: {{ formatDate(execution.started_at) }}</span>
          </div>
          <div v-if="execution.completed_at" class="d-flex align-center mb-1">
            <v-icon icon="mdi-clock-end" size="small" class="me-1" />
            <span class="text-body-small">Completed: {{ formatDate(execution.completed_at) }}</span>
          </div>
          <div
            v-else-if="execution.status === 'running' && execution.started_at"
            class="d-flex align-center mb-1"
          >
            <v-icon icon="mdi-clock" size="small" class="me-1" />
            <span class="text-body-small">{{ calculateDuration(execution.started_at, now) }}</span>
          </div>
        </div>
      </div>

      <!-- Step Progress -->
      <div v-if="execution.steps && execution.steps.length > 0" class="mb-4">
        <div class="text-body-medium font-weight-medium mb-3">Hunt Steps</div>
        <div class="step-list">
          <div
            v-for="(step, index) in execution.steps"
            :key="step.id"
            class="step-item d-flex align-center mb-2"
          >
            <!-- Step Status Icon -->
            <v-avatar :color="getStatusColor(step.status)" size="24" class="me-3">
              <v-icon :icon="getStatusIcon(step.status)" color="white" size="small" />
            </v-avatar>

            <!-- Step Info -->
            <div class="flex-grow-1 text-truncate">
              <div class="text-body-medium text-truncate">
                {{ step.step_id || `Step ${index + 1}` }}
              </div>
              <div class="text-body-small text-medium-emphasis text-truncate">
                {{ step.plugin_name }}
              </div>
            </div>

            <!-- Step Status -->
            <v-chip :color="getStatusColor(step.status)" variant="flat" size="x-small">
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
        <div class="text-body-medium font-weight-medium mb-1">
          {{ execution.status === 'failed' ? 'Hunt Failed' : 'Some Steps Failed' }}
        </div>
        <div v-if="failedSteps.length > 0" class="text-body-small">
          Failed steps: {{ failedSteps.map((s) => s.step_id).join(', ') }}
        </div>
      </v-alert>

      <!-- Results Summary -->
      <div v-if="execution.status === 'completed' || execution.status === 'partial'" class="mb-4">
        <div class="text-body-medium font-weight-medium mb-2">Results Summary</div>
        <div class="d-flex align-center flex-wrap">
          <div class="d-flex align-center me-4 mb-1">
            <v-icon icon="mdi-check-circle" color="success" size="small" class="me-1" />
            <span class="text-body-small">{{ completedSteps.length }} steps completed</span>
          </div>
          <div v-if="failedSteps.length > 0" class="d-flex align-center mb-1">
            <v-icon icon="mdi-alert-circle" color="error" size="small" class="me-1" />
            <span class="text-body-small">{{ failedSteps.length }} steps failed</span>
          </div>
        </div>
      </div>
    </v-card-text>

    <!-- Actions -->
    <v-card-actions class="pa-3 pa-sm-4 pt-0 flex-wrap">
      <v-btn
        v-if="['pending', 'running'].includes(execution.status)"
        color="error"
        variant="outlined"
        size="small"
        @click="$emit('cancel', execution.id)"
        :loading="cancelling"
        :disabled="cancelling"
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
import ExecutionWaiting from '@/components/ExecutionWaiting.vue'
import { computed } from 'vue'
import { useNow } from '@/composables/useNow'
import {
  calculateDuration,
  formatHuntExecutionTitle,
  getStatusText,
  getStatusColor,
  getStatusIcon,
} from '@/utils/huntDisplayUtils'
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

const now = useNow(() => props.execution.status === 'running')

// Computed properties
const statusColor = computed(() => getStatusColor(props.execution.status))
const statusIcon = computed(() => getStatusIcon(props.execution.status))

const statusText = computed(() => getStatusText(props.execution.status, true))

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
</script>

<style scoped>
.hunt-progress-card {
  min-height: 300px;
  width: 100%;
  overflow: hidden;
}

.step-list {
  max-height: 200px;
  overflow: hidden auto;
}

.step-item {
  border-radius: 8px;
  padding: 8px;
  transition: background-color 0.2s ease;
  min-width: 0; /* Enable text truncation in flexbox */
}

.step-item:hover {
  background-color: rgb(var(--v-theme-surface-variant), 0.1);
}

/* Ensure proper text truncation */
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive adjustments */
@media (width <= 600px) {
  .hunt-progress-card {
    min-height: 280px;
  }
}

/* Prevent overflow on timing information */
.timing-info {
  overflow: hidden;
}
</style>
