<template>
  <BaseDashboard :error="error" :loading="loading" :title="pageTitle">
    <!-- Header Actions -->
    <template #header-actions>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="white"
          variant="text"
          prepend-icon="mdi-refresh"
          @click="refreshExecution"
          :loading="loading"
        >
          Refresh
        </v-btn>
        <v-menu v-if="hasResults">
          <template #activator="{ props }">
            <v-btn color="white" prepend-icon="mdi-download" v-bind="props" variant="outlined">
              Export
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-file-pdf-box"
              title="Export as PDF"
              @click="exportPDF"
              :disabled="exportingPDF"
            />
            <v-list-item prepend-icon="mdi-code-json" title="Export as JSON" @click="exportJSON" />
          </v-list>
        </v-menu>
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
          color="white"
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
          <v-icon icon="mdi-information" color="primary" size="large" class="me-3" />
          <div class="flex-grow-1">
            <div class="text-h6 font-weight-bold">Execution Information</div>
            <div class="text-body-2 text-medium-emphasis">
              Details and results for this hunt execution
            </div>
          </div>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-6">
          <!-- Execution Details -->
          <v-row>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Hunt Name
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ execution.hunt?.display_name || 'N/A' }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Status
                </v-list-item-subtitle>
                <v-chip
                  :color="statusColor"
                  size="small"
                  variant="tonal"
                  :prepend-icon="statusIcon"
                >
                  {{ statusText }}
                </v-chip>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Case
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ execution.case?.case_number || `Case #${execution.case_id}` }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Category
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ displayCategory }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Started By
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ execution.created_by?.username || `User #${execution.created_by_id}` }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  Started At
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ formatDate(execution.started_at) }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
                  {{ execution.completed_at ? 'Completed At' : 'Duration' }}
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-1">
                  {{ execution.completed_at ? formatDate(execution.completed_at) : elapsedTime }}
                </v-list-item-title>
              </div>
            </v-col>
          </v-row>

          <!-- Initial Parameters -->
          <div
            v-if="
              execution.initial_parameters && Object.keys(execution.initial_parameters).length > 0
            "
          >
            <v-divider class="my-4" />
            <div class="text-subtitle-1 font-weight-medium mb-3">Hunt Parameters</div>
            <v-table density="compact">
              <tbody>
                <tr v-for="(value, key) in execution.initial_parameters" :key="key">
                  <td class="text-subtitle-2 font-weight-medium" style="width: 40%">
                    {{ formatParameterName(key) }}
                  </td>
                  <td class="text-body-2">{{ value }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>
      </v-card>

      <!-- Main Content Section -->
      <!-- Real-time Log (for running executions) -->
      <v-card v-if="execution.status === 'running'" class="mb-6" variant="outlined">
        <v-card-title class="pa-4">
          <v-icon class="me-2" icon="mdi-console" />
          Live Execution Log
          <v-spacer />
          <v-btn icon="mdi-refresh" size="small" variant="text" @click="refreshLog" />
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-0">
          <div class="execution-log">
            <div
              v-for="(logEntry, index) in executionLog"
              :key="index"
              :class="getLogEntryClass(logEntry.type)"
              class="log-entry pa-3"
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

      <!-- Hunt Results -->
      <v-card class="mb-6" variant="outlined">
        <v-card-title class="pa-4">
          <v-icon class="me-2" icon="mdi-chart-box" />
          Hunt Results
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <!-- Summary Statistics -->
          <HuntResultsSummary
            :context-data="execution.context_data"
            :execution="execution"
            @view-evidence="viewEvidence"
          />

          <!-- Step Results Section -->
          <v-divider class="my-4" />

          <div class="text-h6 mb-3">Step Results</div>
          <div v-if="filteredSteps.length > 0">
            <v-expansion-panels variant="accordion">
              <v-expansion-panel v-for="(step, index) in filteredSteps" :key="step.id">
                <v-expansion-panel-title>
                  <div class="d-flex align-center flex-grow-1">
                    <v-avatar :color="getStatusColor(step.status)" class="me-3" size="32">
                      <v-icon :icon="getStatusIcon(step.status)" color="white" size="small" />
                    </v-avatar>
                    <div class="flex-grow-1">
                      <div class="text-body-1 font-weight-medium">
                        Step {{ index + 1 }}: {{ step.plugin_name }}
                      </div>
                      <div class="text-caption text-medium-emphasis">
                        {{ step.step_id }} • {{ formatDuration(step) }}
                      </div>
                    </div>
                    <v-chip
                      :color="getStatusColor(step.status)"
                      class="mr-2"
                      size="small"
                      variant="flat"
                    >
                      {{ step.status }}
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <HuntStepResults :step="step" :step-number="index + 1" />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
          <div v-else class="text-center pa-8">
            <v-icon class="mb-2" color="grey" icon="mdi-information" size="48" />
            <div class="text-body-1">No steps available</div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Created Evidence -->
      <v-card v-if="createdEvidence.length > 0" class="mb-6" variant="outlined">
        <v-card-title class="pa-4">
          <v-icon class="me-2" icon="mdi-folder-multiple" />
          Created Evidence
          <v-spacer />
          <v-chip size="small" variant="outlined"> {{ createdEvidence.length }} items </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-list density="compact">
            <v-list-item
              v-for="evidence in createdEvidence"
              :key="evidence.id"
              :subtitle="evidence.folder_path"
              :title="evidence.title"
              class="cursor-pointer"
              prepend-icon="mdi-file"
              @click="viewEvidence(evidence)"
            >
              <template #append>
                <v-chip size="x-small" variant="text">
                  {{ formatFileSize(evidence.file_size) }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </div>

    <!-- Step Output Modal -->
    <v-dialog v-model="showStepOutputModal" max-width="800px">
      <v-card>
        <v-card-title class="pa-4"> Step Output: {{ selectedStep?.step_id }} </v-card-title>
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHuntStore } from '@/stores/huntStore.js'
import { useNotifications } from '@/composables/useNotifications'
import { formatDate } from '@/composables/dateUtils'
import {
  calculateDuration,
  exportToJSON,
  formatFileSize,
  formatParameterName,
  formatTime,
  getLogEntryClass,
  getStatusColor,
  getStatusIcon,
  getStatusText,
} from '@/utils/huntDisplayUtils'
import BaseDashboard from '@/components/BaseDashboard.vue'
import HuntResultsSummary from '@/components/hunts/HuntResultsSummary.vue'
import HuntStepResults from '@/components/hunts/HuntStepResults.vue'

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
const exportingPDF = ref(false)
let elapsedInterval = null

// Computed properties
const executionId = computed(() => parseInt(route.params.id))

const pageTitle = computed(() => {
  return `Hunt Execution #${executionId.value}`
})

const statusColor = computed(() => {
  if (!execution.value) return 'grey'
  return getStatusColor(execution.value.status)
})

const statusIcon = computed(() => {
  if (!execution.value) return 'mdi-help'
  return getStatusIcon(execution.value.status)
})

const statusText = computed(() => {
  if (!execution.value) return 'Unknown'
  return getStatusText(execution.value.status)
})

const hasResults = computed(() => {
  return execution.value?.status === 'completed' || execution.value?.status === 'partial'
})

const filteredSteps = computed(() => {
  return execution.value?.steps || []
})

const createdEvidence = computed(() => {
  // Extract evidence references from context data
  if (!execution.value?.context_data?.evidence_refs) return []
  // This would need backend support to fetch actual evidence items
  return []
})

const displayCategory = computed(() => {
  // Try hunt_category first, then hunt.category
  const category = execution.value?.hunt_category || execution.value?.hunt?.category
  if (!category) return 'N/A'

  // Map hunt categories to display categories (matching HuntCatalog filter logic)
  const categoryMapping = {
    person: 'Person',
    domain: 'Network',
    network: 'Network',
    company: 'Company',
    general: 'Other',
    other: 'Other',
  }

  return (
    categoryMapping[category.toLowerCase()] ||
    category.charAt(0).toUpperCase() + category.slice(1).toLowerCase()
  )
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

const exportPDF = async () => {
  try {
    exportingPDF.value = true
    showNotification('PDF export functionality not yet implemented', 'info')
    // TODO: Implement PDF export
  } catch (error) {
    console.error('Failed to export PDF:', error)
    showNotification('Failed to export PDF', 'error')
  } finally {
    exportingPDF.value = false
  }
}

const exportJSON = () => {
  try {
    const data = {
      execution: execution.value,
      timestamp: new Date().toISOString(),
      export_version: '1.0',
    }

    exportToJSON(data, `hunt_execution_${executionId.value}_results.json`)
    showNotification('Results exported successfully', 'success')
  } catch (error) {
    console.error('Failed to export JSON:', error)
    showNotification('Failed to export JSON', 'error')
  }
}

const viewEvidence = (evidence) => {
  // Navigate to evidence view
  router.push(`/case/${execution.value.case_id}?tab=evidence&highlight=${evidence.id}`)
}

const formatLogTime = (timestamp) => {
  return formatTime(timestamp)
}

const formatDuration = (step) => {
  if (!step.started_at || !step.completed_at) return ''
  return calculateDuration(step.started_at, step.completed_at)
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
watch(
  () => huntStore.activeExecutions[executionId.value],
  (updatedExecution) => {
    if (updatedExecution) {
      execution.value = updatedExecution

      // Stop timer if execution is no longer running
      if (updatedExecution.status !== 'running') {
        stopElapsedTimer()

        // No need to auto-switch since results is the default tab
      }
    }
  },
)
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

.cursor-pointer {
  cursor: pointer;
}

.cursor-pointer:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
