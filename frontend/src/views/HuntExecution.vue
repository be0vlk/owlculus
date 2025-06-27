<template>
  <BaseDashboard
    :title="pageTitle"
    :loading="loading"
    :error="error"
  >
    <!-- Header Actions -->
    <template #header-actions>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="primary"
          variant="text"
          prepend-icon="mdi-refresh"
          @click="refreshExecution"
          :loading="loading"
        >
          Refresh
        </v-btn>
        <v-btn
          v-if="execution?.status === 'running'"
          color="error"
          variant="outlined"
          prepend-icon="mdi-stop"
          @click="handleCancelExecution"
          :loading="cancelling"
        >
          Cancel Hunt
        </v-btn>
        <v-btn
          variant="text"
          prepend-icon="mdi-arrow-left"
          @click="$router.push('/hunts')"
        >
          Back to Hunts
        </v-btn>
      </div>
    </template>

    <!-- Loading State -->
    <template #loading>
      <v-card variant="outlined">
        <v-skeleton-loader type="article" />
      </v-card>
    </template>

    <!-- Main Content -->
    <div v-if="execution">
      <!-- Execution Overview Card -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-avatar :color="statusColor" size="48" class="me-4">
            <v-icon :icon="statusIcon" color="white" />
          </v-avatar>
          <div class="flex-grow-1">
            <div class="text-h5 font-weight-bold">{{ execution.hunt?.display_name }}</div>
            <div class="text-subtitle-1 text-medium-emphasis">
              Execution #{{ execution.id }} • {{ execution.hunt?.category }}
            </div>
          </div>
          <v-chip :color="statusColor" variant="flat" size="large">
            {{ statusText }}
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <!-- Progress Section -->
          <div class="mb-4">
            <div class="d-flex align-center justify-space-between mb-2">
              <span class="text-h6">Overall Progress</span>
              <span class="text-h6">{{ Math.round(execution.progress * 100) }}%</span>
            </div>
            <v-progress-linear
              :model-value="execution.progress * 100"
              :color="statusColor"
              height="12"
              rounded
            />
          </div>

          <!-- Execution Details -->
          <v-row>
            <v-col cols="12" md="6">
              <div class="mb-3">
                <div class="text-body-2 font-weight-medium mb-1">Case</div>
                <v-chip prepend-icon="mdi-folder" variant="outlined">
                  Case #{{ execution.case_id }}
                </v-chip>
              </div>
              <div class="mb-3">
                <div class="text-body-2 font-weight-medium mb-1">Started</div>
                <div class="text-body-1">{{ formatDateTime(execution.started_at) }}</div>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-3">
                <div class="text-body-2 font-weight-medium mb-1">Created By</div>
                <div class="text-body-1">User #{{ execution.created_by_id }}</div>
              </div>
              <div class="mb-3">
                <div class="text-body-2 font-weight-medium mb-1">
                  {{ execution.completed_at ? 'Completed' : 'Duration' }}
                </div>
                <div class="text-body-1">
                  {{ execution.completed_at ? formatDateTime(execution.completed_at) : elapsedTime }}
                </div>
              </div>
            </v-col>
          </v-row>

          <!-- Initial Parameters -->
          <div v-if="execution.initial_parameters && Object.keys(execution.initial_parameters).length > 0" class="mt-4">
            <div class="text-h6 mb-3">Hunt Parameters</div>
            <v-table density="compact">
              <tbody>
                <tr v-for="(value, key) in execution.initial_parameters" :key="key">
                  <td class="font-weight-medium">{{ formatParameterName(key) }}</td>
                  <td>{{ value }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>
      </v-card>

      <!-- Hunt Steps -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="pa-4">
          <v-icon icon="mdi-play-box-multiple" class="me-2" />
          Hunt Steps
          <v-spacer />
          <v-chip size="small" variant="outlined">
            {{ execution.steps?.length || 0 }} steps
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-0">
          <div v-if="execution.steps && execution.steps.length > 0">
            <HuntStepProgress
              v-for="(step, index) in execution.steps"
              :key="step.id"
              :step="step"
              :step-number="index + 1"
              :is-last="index === execution.steps.length - 1"
              @view-output="handleViewStepOutput"
              @view-error="handleViewStepError"
            />
          </div>
          <div v-else class="text-center pa-8">
            <v-icon icon="mdi-information" size="48" color="grey" class="mb-2" />
            <div class="text-body-1">No step information available</div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Real-time Log -->
      <v-card v-if="execution.status === 'running'" variant="outlined" class="mb-6">
        <v-card-title class="pa-4">
          <v-icon icon="mdi-console" class="me-2" />
          Live Execution Log
          <v-spacer />
          <v-btn
            icon="mdi-refresh"
            variant="text"
            size="small"
            @click="refreshLog"
          />
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-0">
          <div class="execution-log">
            <div
              v-for="(logEntry, index) in executionLog"
              :key="index"
              class="log-entry pa-3"
              :class="getLogEntryClass(logEntry.type)"
            >
              <span class="text-caption">{{ formatLogTime(logEntry.timestamp) }}</span>
              <span class="ml-2">{{ logEntry.message }}</span>
            </div>
            <div v-if="executionLog.length === 0" class="text-center pa-4 text-medium-emphasis">
              Waiting for log entries...
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Results Summary -->
      <v-card
        v-if="execution.status === 'completed' || execution.status === 'partial'"
        variant="outlined"
      >
        <v-card-title class="pa-4">
          <v-icon icon="mdi-file-document" class="me-2" />
          Execution Results
          <v-spacer />
          <v-btn
            color="primary"
            variant="elevated"
            prepend-icon="mdi-eye"
            @click="viewResults"
          >
            View Full Results
          </v-btn>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <HuntResultsSummary
            :execution="execution"
            :context-data="execution.context_data"
          />
        </v-card-text>
      </v-card>
    </div>

    <!-- Step Output Modal -->
    <v-dialog v-model="showStepOutputModal" max-width="800px">
      <v-card>
        <v-card-title class="pa-4">
          Step Output: {{ selectedStep?.step_id }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <pre class="step-output">{{ JSON.stringify(selectedStep?.output, null, 2) }}</pre>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn @click="showStepOutputModal = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Step Error Modal -->
    <v-dialog v-model="showStepErrorModal" max-width="600px">
      <v-card>
        <v-card-title class="pa-4 bg-error text-white">
          Step Error: {{ selectedStep?.step_id }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert type="error" variant="tonal">
            {{ selectedStep?.error_details }}
          </v-alert>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn @click="showStepErrorModal = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </BaseDashboard>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHuntStore } from '@/stores/hunt'
import { useNotifications } from '@/composables/useNotifications'
import BaseDashboard from '@/components/BaseDashboard.vue'
import HuntStepProgress from '@/components/hunts/HuntStepProgress.vue'
import HuntResultsSummary from '@/components/hunts/HuntResultsSummary.vue'

// Route and store
const route = useRoute()
const router = useRouter()
const huntStore = useHuntStore()
const { showNotification } = useNotifications()

// Local state
const loading = ref(true)
const error = ref(null)
const execution = ref(null)
const cancelling = ref(false)
const selectedStep = ref(null)
const showStepOutputModal = ref(false)
const showStepErrorModal = ref(false)
const executionLog = ref([])
const elapsedTime = ref('')
let elapsedInterval = null

// Computed properties
const executionId = computed(() => parseInt(route.params.id))

const pageTitle = computed(() => {
  if (execution.value?.hunt) {
    return `${execution.value.hunt.display_name} - Execution #${execution.value.id}`
  }
  return `Hunt Execution #${executionId.value}`
})

const statusColor = computed(() => {
  if (!execution.value) return 'grey'
  switch (execution.value.status) {
    case 'pending': return 'grey'
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'partial': return 'warning'
    case 'failed': return 'error'
    case 'cancelled': return 'grey'
    default: return 'grey'
  }
})

const statusIcon = computed(() => {
  if (!execution.value) return 'mdi-help'
  switch (execution.value.status) {
    case 'pending': return 'mdi-clock-outline'
    case 'running': return 'mdi-play'
    case 'completed': return 'mdi-check'
    case 'partial': return 'mdi-alert'
    case 'failed': return 'mdi-close'
    case 'cancelled': return 'mdi-stop'
    default: return 'mdi-help'
  }
})

const statusText = computed(() => {
  if (!execution.value) return 'Unknown'
  switch (execution.value.status) {
    case 'pending': return 'Pending'
    case 'running': return 'Running'
    case 'completed': return 'Completed'
    case 'partial': return 'Partial'
    case 'failed': return 'Failed'
    case 'cancelled': return 'Cancelled'
    default: return 'Unknown'
  }
})

// Methods
const loadExecution = async () => {
  try {
    loading.value = true
    error.value = null
    
    execution.value = await huntStore.getExecution(executionId.value, true)
    
    // Subscribe to real-time updates if running
    if (execution.value.status === 'running') {
      huntStore.subscribeToExecution(executionId.value)
      startElapsedTimer()
    }
  } catch (err) {
    error.value = err.message || 'Failed to load execution details'
    console.error('Failed to load execution:', err)
  } finally {
    loading.value = false
  }
}

const refreshExecution = async () => {
  await loadExecution()
}

const handleCancelExecution = async () => {
  try {
    cancelling.value = true
    await huntStore.cancelExecution(executionId.value)
    showNotification('Hunt execution cancelled', 'info')
    await loadExecution()
  } catch (err) {
    showNotification(err.message || 'Failed to cancel execution', 'error')
  } finally {
    cancelling.value = false
  }
}

const handleViewStepOutput = (step) => {
  selectedStep.value = step
  showStepOutputModal.value = true
}

const handleViewStepError = (step) => {
  selectedStep.value = step
  showStepErrorModal.value = true
}

const viewResults = () => {
  router.push(`/hunts/execution/${executionId.value}/results`)
}

const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString()
}

const formatLogTime = (timestamp) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}

const formatParameterName = (paramName) => {
  return paramName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const getLogEntryClass = (type) => {
  switch (type) {
    case 'error': return 'log-error'
    case 'warning': return 'log-warning'
    case 'info': return 'log-info'
    default: return 'log-default'
  }
}

const refreshLog = () => {
  // Placeholder for log refresh functionality
  console.log('Refreshing log...')
}

const updateElapsedTime = () => {
  if (!execution.value?.started_at || execution.value.status !== 'running') {
    elapsedTime.value = ''
    return
  }

  const startTime = new Date(execution.value.started_at)
  const now = new Date()
  const diff = now - startTime

  const minutes = Math.floor(diff / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  
  if (minutes > 0) {
    elapsedTime.value = `${minutes}m ${seconds}s`
  } else {
    elapsedTime.value = `${seconds}s`
  }
}

const startElapsedTimer = () => {
  updateElapsedTime()
  elapsedInterval = setInterval(updateElapsedTime, 1000)
}

const stopElapsedTimer = () => {
  if (elapsedInterval) {
    clearInterval(elapsedInterval)
    elapsedInterval = null
  }
}

// Lifecycle
onMounted(async () => {
  await loadExecution()
})

onUnmounted(() => {
  stopElapsedTimer()
  huntStore.unsubscribeFromExecution(executionId.value)
})

// Watch for execution updates from store
import { watch } from 'vue'
watch(() => huntStore.activeExecutions[executionId.value], (updatedExecution) => {
  if (updatedExecution) {
    execution.value = updatedExecution
    
    // Stop timer if execution is no longer running
    if (updatedExecution.status !== 'running') {
      stopElapsedTimer()
    }
  }
})
</script>

<style scoped>
.execution-log {
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background-color: rgb(var(--v-theme-surface-variant));
}

.log-entry {
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
  white-space: pre-wrap;
}

.log-error {
  background-color: rgba(var(--v-theme-error), 0.1);
  color: rgb(var(--v-theme-error));
}

.log-warning {
  background-color: rgba(var(--v-theme-warning), 0.1);
  color: rgb(var(--v-theme-warning));
}

.log-info {
  background-color: rgba(var(--v-theme-info), 0.1);
  color: rgb(var(--v-theme-info));
}

.log-default {
  color: rgb(var(--v-theme-on-surface));
}

.step-output {
  background-color: rgb(var(--v-theme-surface-variant));
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.v-table tbody td {
  padding: 8px 16px;
}
</style>