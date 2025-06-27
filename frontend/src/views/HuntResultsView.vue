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
          @click="loadResults"
          :loading="loading"
        >
          Refresh
        </v-btn>
        <v-menu>
          <template #activator="{ props }">
            <v-btn
              color="primary"
              variant="outlined"
              prepend-icon="mdi-download"
              v-bind="props"
              :disabled="!hasResults"
            >
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
            <v-list-item
              prepend-icon="mdi-code-json"
              title="Export as JSON"
              @click="exportJSON"
            />
          </v-list>
        </v-menu>
        <v-btn
          variant="text"
          prepend-icon="mdi-arrow-left"
          @click="$router.push(`/hunts/execution/${executionId}`)"
        >
          Back to Execution
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
      <!-- Execution Summary Card -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-avatar :color="getCategoryColor(execution.hunt?.category)" size="48" class="me-4">
            <v-icon :icon="getCategoryIcon(execution.hunt?.category)" color="white" />
          </v-avatar>
          <div class="flex-grow-1">
            <div class="text-h5 font-weight-bold">{{ execution.hunt?.display_name }} Results</div>
            <div class="text-subtitle-1 text-medium-emphasis">
              Execution #{{ execution.id }} • Case #{{ execution.case_id }}
            </div>
          </div>
          <v-chip :color="getStatusColor(execution.status)" variant="flat" size="large">
            {{ getStatusText(execution.status) }}
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-row>
            <v-col cols="12" md="3">
              <div class="text-body-2 font-weight-medium mb-1">Started</div>
              <div class="text-body-1">{{ formatDateTime(execution.started_at) }}</div>
            </v-col>
            <v-col cols="12" md="3">
              <div class="text-body-2 font-weight-medium mb-1">Completed</div>
              <div class="text-body-1">{{ formatDateTime(execution.completed_at) || 'In Progress' }}</div>
            </v-col>
            <v-col cols="12" md="3">
              <div class="text-body-2 font-weight-medium mb-1">Duration</div>
              <div class="text-body-1">{{ calculateDuration(execution) }}</div>
            </v-col>
            <v-col cols="12" md="3">
              <div class="text-body-2 font-weight-medium mb-1">Steps Completed</div>
              <div class="text-body-1">
                {{ completedSteps }} / {{ totalSteps }}
                <span class="text-medium-emphasis ml-1">({{ Math.round(execution.progress * 100) }}%)</span>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- Results Summary -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="pa-4">
          <v-icon icon="mdi-chart-box" class="me-2" />
          Results Summary
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <HuntResultsSummary
            :execution="execution"
            :context-data="execution.context_data"
          />
        </v-card-text>
      </v-card>

      <!-- Step-by-Step Results -->
      <v-card variant="outlined" class="mb-6">
        <v-card-title class="pa-4">
          <v-icon icon="mdi-format-list-numbered" class="me-2" />
          Step Results
          <v-spacer />
          <v-btn-toggle
            v-model="stepFilter"
            variant="outlined"
            density="compact"
            divided
          >
            <v-btn value="all" size="small">All</v-btn>
            <v-btn value="completed" size="small">Completed</v-btn>
            <v-btn value="failed" size="small">Failed</v-btn>
          </v-btn-toggle>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-0">
          <div v-if="filteredSteps.length > 0">
            <v-expansion-panels variant="accordion">
              <v-expansion-panel
                v-for="(step, index) in filteredSteps"
                :key="step.id"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center flex-grow-1">
                    <v-avatar
                      :color="getStepStatusColor(step.status)"
                      size="32"
                      class="me-3"
                    >
                      <v-icon
                        :icon="getStepStatusIcon(step.status)"
                        color="white"
                        size="small"
                      />
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
                      :color="getStepStatusColor(step.status)"
                      variant="flat"
                      size="small"
                      class="mr-2"
                    >
                      {{ step.status }}
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <HuntStepResults
                    :step="step"
                    :step-number="index + 1"
                  />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
          <div v-else class="text-center pa-8">
            <v-icon icon="mdi-information" size="48" color="grey" class="mb-2" />
            <div class="text-body-1">No {{ stepFilter }} steps found</div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Evidence Created -->
      <v-card v-if="createdEvidence.length > 0" variant="outlined">
        <v-card-title class="pa-4">
          <v-icon icon="mdi-folder-multiple" class="me-2" />
          Created Evidence
          <v-spacer />
          <v-chip size="small" variant="outlined">
            {{ createdEvidence.length }} items
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-list density="compact">
            <v-list-item
              v-for="evidence in createdEvidence"
              :key="evidence.id"
              :title="evidence.title"
              :subtitle="evidence.folder_path"
              prepend-icon="mdi-file"
              @click="viewEvidence(evidence)"
              class="cursor-pointer"
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
  </BaseDashboard>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHuntStore } from '@/stores/hunt'
import { useNotifications } from '@/composables/useNotifications'
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
const stepFilter = ref('all')
const exportingPDF = ref(false)

// Computed properties
const executionId = computed(() => parseInt(route.params.id))

const pageTitle = computed(() => {
  if (execution.value?.hunt) {
    return `${execution.value.hunt.display_name} - Results`
  }
  return 'Hunt Results'
})

const hasResults = computed(() => {
  return execution.value?.status === 'completed' || execution.value?.status === 'partial'
})

const totalSteps = computed(() => execution.value?.steps?.length || 0)

const completedSteps = computed(() => {
  if (!execution.value?.steps) return 0
  return execution.value.steps.filter(step => 
    step.status === 'completed' || step.status === 'failed'
  ).length
})

const filteredSteps = computed(() => {
  if (!execution.value?.steps) return []
  
  switch (stepFilter.value) {
    case 'completed':
      return execution.value.steps.filter(step => step.status === 'completed')
    case 'failed':
      return execution.value.steps.filter(step => step.status === 'failed')
    default:
      return execution.value.steps
  }
})

const createdEvidence = computed(() => {
  // Extract evidence references from context data
  if (!execution.value?.context_data?.evidence_refs) return []
  // This would need backend support to fetch actual evidence items
  return []
})

// Methods
const loadResults = async () => {
  try {
    loading.value = true
    error.value = null
    
    execution.value = await huntStore.getExecution(executionId.value, true)
    
    if (!execution.value) {
      throw new Error('Execution not found')
    }
  } catch (err) {
    error.value = err.message || 'Failed to load execution results'
    console.error('Failed to load results:', err)
  } finally {
    loading.value = false
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
      export_version: '1.0'
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `hunt_execution_${executionId.value}_results.json`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
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

const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString()
}

const calculateDuration = (execution) => {
  if (!execution.started_at) return 'N/A'
  
  const startTime = new Date(execution.started_at)
  const endTime = execution.completed_at ? new Date(execution.completed_at) : new Date()
  const diffMs = endTime - startTime
  
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  
  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes % 60}m`
  } else if (diffMinutes > 0) {
    return `${diffMinutes}m ${diffSeconds % 60}s`
  } else {
    return `${diffSeconds}s`
  }
}

const formatDuration = (step) => {
  if (!step.started_at || !step.completed_at) return ''
  
  const start = new Date(step.started_at)
  const end = new Date(step.completed_at)
  const diff = end - start
  
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Status helpers
const getStatusColor = (status) => {
  switch (status) {
    case 'pending': return 'grey'
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'partial': return 'warning'
    case 'failed': return 'error'
    case 'cancelled': return 'grey'
    default: return 'grey'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'pending': return 'Pending'
    case 'running': return 'Running'
    case 'completed': return 'Completed'
    case 'partial': return 'Partial Success'
    case 'failed': return 'Failed'
    case 'cancelled': return 'Cancelled'
    default: return 'Unknown'
  }
}

const getStepStatusColor = (status) => {
  switch (status) {
    case 'pending': return 'grey'
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'failed': return 'error'
    case 'skipped': return 'warning'
    default: return 'grey'
  }
}

const getStepStatusIcon = (status) => {
  switch (status) {
    case 'pending': return 'mdi-clock-outline'
    case 'running': return 'mdi-play'
    case 'completed': return 'mdi-check'
    case 'failed': return 'mdi-close'
    case 'skipped': return 'mdi-skip-next'
    default: return 'mdi-help'
  }
}

const getCategoryIcon = (category) => {
  const iconMap = {
    person: 'mdi-account',
    domain: 'mdi-web',
    company: 'mdi-office-building',
    ip: 'mdi-ip-network',
    phone: 'mdi-phone',
    email: 'mdi-email',
    general: 'mdi-magnify'
  }
  return iconMap[category] || iconMap.general
}

const getCategoryColor = (category) => {
  const colorMap = {
    person: 'blue',
    domain: 'green',
    company: 'orange',
    ip: 'purple',
    phone: 'teal',
    email: 'red',
    general: 'grey'
  }
  return colorMap[category] || colorMap.general
}

// Lifecycle
onMounted(async () => {
  await loadResults()
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}

.cursor-pointer:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.04);
}
</style>