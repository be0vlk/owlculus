<template>
  <BaseDashboard :loading="loading && !execution" :title="pageTitle">
    <!-- Header Actions -->
    <template #header-actions>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="white"
          variant="text"
          prepend-icon="mdi-refresh"
          @click="loadExecution"
          :loading="loading"
        >
          Refresh
        </v-btn>
        <v-menu v-if="canExport">
          <template #activator="{ props }">
            <v-btn color="white" prepend-icon="mdi-download" v-bind="props" variant="outlined">
              Export
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-file-pdf-box"
              title="Export as PDF"
              @click="exportExecution('pdf')"
              :disabled="exportingPDF"
            />
            <v-list-item
              prepend-icon="mdi-code-json"
              title="Export as JSON"
              @click="exportExecution('json')"
            />
          </v-list>
        </v-menu>
        <v-btn
          v-if="['pending', 'running'].includes(execution?.status)"
          color="error"
          variant="outlined"
          prepend-icon="mdi-stop"
          @click="handleCancelExecution"
          :loading="cancelling"
          :disabled="cancelling"
        >
          Cancel Hunt
        </v-btn>
        <v-btn
          color="white"
          variant="text"
          prepend-icon="mdi-arrow-left"
          @click="$router.push(`/case/${route.params.caseId}/hunts`)"
        >
          Back to Hunts
        </v-btn>
      </div>
    </template>

    <!-- Loading State -->
    <v-alert v-if="huntStore.error" type="error" role="alert" class="mb-4">
      {{ huntStore.error }}
    </v-alert>
    <template #loading>
      <v-card variant="outlined">
        <v-skeleton-loader type="article" />
      </v-card>
    </template>

    <!-- Main Content -->
    <div v-if="execution">
      <ExecutionWaiting :execution="execution" />
      <v-alert v-if="execution.error" type="error" role="alert" class="mb-4">
        {{ execution.error.message }}
      </v-alert>
      <!-- Execution Overview Card -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-icon icon="mdi-information" color="primary" size="large" class="me-3" />
          <div class="flex-grow-1">
            <div class="text-title-large font-weight-bold">Execution Information</div>
            <div class="text-body-medium text-medium-emphasis">
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
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Hunt Name
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{ execution.hunt?.display_name || 'N/A' }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Status
                </v-list-item-subtitle>
                <v-chip
                  :color="getStatusColor(execution.status)"
                  size="small"
                  variant="tonal"
                  :prepend-icon="getStatusIcon(execution.status)"
                >
                  {{ getStatusText(execution.status) }}
                </v-chip>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Case
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{ execution.case?.case_number || `Case #${execution.case_id}` }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Category
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{ getDisplayCategory(execution.hunt_category || execution.hunt?.category) }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Started By
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{ execution.created_by?.username || `User #${execution.created_by_id}` }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  Started At
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{ formatDate(execution.started_at) }}
                </v-list-item-title>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="mb-4">
                <v-list-item-subtitle class="text-title-small font-weight-medium mb-1">
                  {{ execution.completed_at ? 'Completed At' : 'Duration' }}
                </v-list-item-subtitle>
                <v-list-item-title class="text-body-large">
                  {{
                    execution.completed_at
                      ? formatDate(execution.completed_at)
                      : execution.status === 'running' && execution.started_at
                        ? calculateDuration(execution.started_at, now)
                        : ''
                  }}
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
            <div class="text-body-large font-weight-medium mb-3">Hunt Parameters</div>
            <v-table class="hunt-table" density="compact">
              <tbody>
                <tr v-for="(value, key) in execution.initial_parameters" :key="key">
                  <td class="text-title-small font-weight-medium" style="width: 40%">
                    {{ formatParameterName(key) }}
                  </td>
                  <td class="text-body-medium">{{ value }}</td>
                </tr>
              </tbody>
            </v-table>
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

          <div class="text-title-large mb-3">Step Results</div>
          <div v-if="execution.steps?.length">
            <v-expansion-panels variant="accordion">
              <v-expansion-panel v-for="(step, index) in execution.steps" :key="step.id">
                <v-expansion-panel-title>
                  <div class="d-flex align-center flex-grow-1">
                    <v-avatar :color="getStatusColor(step.status)" class="me-3" size="32">
                      <v-icon :icon="getStatusIcon(step.status)" color="white" size="small" />
                    </v-avatar>
                    <div class="flex-grow-1">
                      <div class="text-body-large font-weight-medium">
                        Step {{ index + 1 }}: {{ step.plugin_name }}
                      </div>
                      <div class="text-body-small text-medium-emphasis">
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
                  <HuntStepResults
                    :step="step"
                    :retrieval-loading="loading"
                    :retrieval-error="huntStore.error"
                    :export-error="exportError"
                    @retry="loadExecution"
                  />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
          <div v-else class="text-center pa-8">
            <v-icon class="mb-2" color="grey" icon="mdi-information" size="48" />
            <div class="text-body-large">No steps available</div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </BaseDashboard>
</template>

<script setup>
import ExecutionWaiting from '@/components/ExecutionWaiting.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHuntStore } from '@/stores/huntStore.js'
import { huntService } from '@/services/hunt'
import { useNotifications } from '@/composables/useNotifications'
import { formatDate } from '@/composables/dateUtils'
import {
  calculateDuration,
  formatParameterName,
  getDisplayCategory,
  getStatusColor,
  getStatusIcon,
  getStatusText,
} from '@/utils/huntDisplayUtils'
import { useNow } from '@/composables/useNow'
import { downloadBlob } from '@/utils/download'
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
const execution = computed(() => {
  const record = huntStore.activeExecutions[executionId.value]
  return record && String(record.case_id) === String(route.params.caseId) ? record : null
})
const cancelling = computed(() => !!huntStore.cancellationPending[executionId.value])
const exportingPDF = ref(false)
const exportError = ref(null)
let workflow = null
let loadGeneration = 0

// Computed properties
const executionId = computed(() => parseInt(route.params.id))
const now = useNow(() => execution.value?.status === 'running')

const pageTitle = computed(() => {
  return `Hunt Execution #${executionId.value}`
})

const canExport = computed(() => {
  return execution.value && !['pending', 'running', 'cancelling'].includes(execution.value.status)
})

// Methods
const loadExecution = async () => {
  const owner = workflow
  const request = ++loadGeneration
  if (!owner?.isCurrent()) return
  try {
    loading.value = true
    const result = await owner.refresh()
    if (!owner.isCurrent() || request !== loadGeneration) return
    if (result && String(result.case_id) !== String(route.params.caseId)) {
      await router.replace(`/case/${result.case_id}/hunts/execution/${result.id}`)
    }
  } catch {
    // The workflow retains read feedback until durable recovery succeeds.
  } finally {
    if (owner.isCurrent() && request === loadGeneration) loading.value = false
  }
}

const handleCancelExecution = async () => {
  const owner = workflow
  try {
    const result = await huntStore.cancelExecution(executionId.value)
    if (result && owner?.isCurrent()) showNotification('Cancellation requested', 'info')
  } catch (err) {
    if (owner?.isCurrent()) showNotification(err.message || 'Failed to cancel execution', 'error')
  }
}

const exportExecution = async (format) => {
  const owner = workflow
  const id = executionId.value
  try {
    exportError.value = null
    exportingPDF.value = format === 'pdf'
    const artifact = await huntService.exportExecution(id, format)
    if (!owner?.isCurrent()) return
    downloadBlob(artifact, `hunt-execution-${id}.${format}`)
    showNotification('Results exported successfully', 'success')
  } catch (error) {
    if (!owner?.isCurrent()) return
    console.error(`Failed to export ${format.toUpperCase()}:`, error)
    exportError.value = `Failed to export ${format.toUpperCase()}`
    showNotification(`Failed to export ${format.toUpperCase()}`, 'error')
  } finally {
    if (owner?.isCurrent()) exportingPDF.value = false
  }
}

const viewEvidence = (evidence) => {
  // Navigate to evidence view
  router.push(`/case/${execution.value.case_id}?tab=evidence&highlight=${evidence.id}`)
}

const formatDuration = (step) => {
  if (!step.started_at || !step.completed_at) return ''
  return calculateDuration(step.started_at, step.completed_at)
}

// Lifecycle
watch(
  () => [route.params.caseId, route.params.id],
  () => {
    workflow = huntStore.openWorkflow({
      caseId: route.params.caseId,
      executionId: executionId.value,
    })
    exportingPDF.value = false
    exportError.value = null
    loadExecution()
  },
  { immediate: true },
)

onBeforeUnmount(() => workflow?.release())
</script>

<style scoped>
.hunt-table tbody td {
  padding: 8px 16px;
}
</style>
