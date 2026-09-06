<template>
  <BaseDashboard :loading="loading && !huntStore.executionHistory.length" title="Hunt Management">
    <!-- Header Actions -->
    <template #header-actions>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="white"
          variant="text"
          prepend-icon="mdi-refresh"
          @click="refreshData"
          :loading="loading"
          :disabled="!caseId"
        >
          Refresh
        </v-btn>
      </div>
    </template>

    <!-- Loading State -->
    <template #loading>
      <v-card variant="outlined">
        <v-skeleton-loader type="table" />
      </v-card>
    </template>

    <v-alert v-if="error || huntStore.error" type="error" role="alert" class="mb-4">
      {{ error || huntStore.error }}
    </v-alert>
    <!-- Main Content -->
    <v-alert v-if="!caseId" type="info">Resolve an accessible case to use Hunts.</v-alert>
    <v-card v-else variant="outlined">
      <!-- Tabs -->
      <v-tabs v-model="activeTab" bg-color="surface" class="px-4">
        <v-tab value="catalog" prepend-icon="mdi-view-grid">
          Available Hunts
          <v-chip v-if="huntStore.availableHunts.length > 0" size="small" class="ml-2">
            {{ huntStore.availableHunts.length }}
          </v-chip>
        </v-tab>
        <v-tab value="active" prepend-icon="mdi-play">
          Active Executions
          <v-chip
            v-if="huntStore.runningExecutions.length > 0"
            class="ml-2"
            color="primary"
            size="small"
          >
            {{ huntStore.runningExecutions.length }}
          </v-chip>
        </v-tab>
        <v-tab prepend-icon="mdi-history" value="history"> Execution History </v-tab>
      </v-tabs>

      <v-divider />

      <!-- Tab Content -->
      <v-tabs-window v-model="activeTab">
        <!-- Available Hunts Tab -->
        <v-tabs-window-item value="catalog">
          <div class="pa-4">
            <HuntCatalog
              :hunts="huntStore.availableHunts"
              :loading="loading"
              :error="error"
              @execute="handleExecuteHunt"
              @view-details="handleViewHuntDetails"
              @retry="refreshData"
            />
          </div>
        </v-tabs-window-item>

        <!-- Active Executions Tab -->
        <v-tabs-window-item value="active">
          <div class="pa-4">
            <!-- Active Executions -->
            <div v-if="huntStore.runningExecutions.length > 0">
              <div class="text-title-large mb-4">Running Executions</div>
              <v-row density="compact">
                <v-col
                  v-for="execution in huntStore.runningExecutions"
                  :key="`running-${execution.id}`"
                  cols="12"
                  sm="6"
                  md="6"
                  lg="4"
                  xl="3"
                  class="d-flex"
                >
                  <HuntProgressCard
                    :execution="execution"
                    :cancelling="cancellingExecutions.has(execution.id)"
                    @cancel="handleCancelExecution"
                    @view-details="handleViewExecutionDetails"
                    class="flex-grow-1"
                  />
                </v-col>
              </v-row>
            </div>

            <!-- Recently Completed -->
            <div v-if="huntStore.completedExecutions.length > 0" class="mt-6">
              <div class="text-title-large mb-4">Recently Completed</div>
              <v-row density="compact">
                <v-col
                  v-for="execution in huntStore.completedExecutions.slice(0, 6)"
                  :key="`completed-${execution.id}`"
                  cols="12"
                  sm="6"
                  md="6"
                  lg="4"
                  xl="3"
                  class="d-flex"
                >
                  <HuntProgressCard
                    :execution="execution"
                    @view-details="handleViewExecutionDetails"
                    class="flex-grow-1"
                  />
                </v-col>
              </v-row>
            </div>

            <!-- Empty State -->
            <div
              v-if="
                huntStore.runningExecutions.length === 0 &&
                huntStore.completedExecutions.length === 0
              "
              class="text-center pa-8"
            >
              <v-icon icon="mdi-play-circle-outline" size="64" color="grey" class="mb-4" />
              <div class="text-title-large mb-2">No Active Executions</div>
              <div class="text-body-medium text-medium-emphasis mb-4">
                Start a hunt from the Available Hunts tab to begin investigating
              </div>
              <v-btn color="primary" @click="activeTab = 'catalog'"> Browse Hunts </v-btn>
            </div>
          </div>
        </v-tabs-window-item>

        <!-- Execution History Tab -->
        <v-tabs-window-item value="history">
          <div class="pa-4">
            <HuntExecutionHistory
              :executions="
                huntStore.executionHistory.filter(
                  (exec) => exec.status !== 'running' && exec.status !== 'pending',
                )
              "
              :loading="historyLoading"
              @view-details="handleViewExecutionDetails"
            />
          </div>
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card>

    <!-- Hunt Execution Modal -->
    <HuntExecutionModal
      v-model="showExecutionModal"
      :hunt="selectedHunt"
      :case-id="caseId"
      :executing="submittingHunt"
      :error="huntSubmissionError"
      @execute="handleExecuteHuntSubmit"
      @cancel="handleExecutionModalCancel"
    />

    <!-- Hunt Details Modal -->
    <HuntDetailsModal
      v-model="showDetailsModal"
      :hunt="selectedHunt"
      @execute="handleExecuteHunt"
      @close="handleDetailsModalClose"
    />
  </BaseDashboard>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useHuntStore } from '@/stores/huntStore.js'
import { useNotifications } from '@/composables/useNotifications'
import BaseDashboard from '@/components/BaseDashboard.vue'
import HuntCatalog from '@/components/hunts/HuntCatalog.vue'
import HuntProgressCard from '@/components/hunts/HuntProgressCard.vue'
import HuntExecutionModal from '@/components/hunts/HuntExecutionModal.vue'
import HuntDetailsModal from '@/components/hunts/HuntDetailsModal.vue'
import HuntExecutionHistory from '@/components/hunts/HuntExecutionHistory.vue'
import { useActiveCaseStore } from '@/stores/activeCase'

// Store and router
const router = useRouter()
const authStore = useAuthStore()
const huntStore = useHuntStore()
const activeCase = useActiveCaseStore()
const caseId = computed(() => activeCase.activeCaseId)
const { showNotification } = useNotifications()

// Local state
const loading = ref(true)
const historyLoading = ref(false)
const error = ref(null)
const activeTab = ref('catalog')
const selectedHunt = ref(null)
const showExecutionModal = ref(false)
const submittingHunt = ref(false)
const huntSubmissionError = ref(null)
const showDetailsModal = ref(false)
const cancellingExecutions = ref(new Set())
let loadGeneration = 0

// Computed properties
const userRole = computed(() => authStore.user?.role)

// Check access permissions
const checkAccess = () => {
  if (userRole.value === 'Analyst') {
    showNotification('Access denied. Analysts cannot access hunt management.', 'error')
    router.push('/cases')
    return false
  }
  return true
}

// Methods
const loadData = async () => {
  const request = ++loadGeneration
  const id = caseId.value
  if (!id || !checkAccess()) {
    huntStore.resetCaseExecutions()
    loading.value = false
    return
  }
  try {
    loading.value = true
    error.value = null
    await Promise.all([huntStore.fetchHunts(), huntStore.getCaseExecutions(id)])
  } catch (err) {
    if (request === loadGeneration) error.value = err.message || 'Failed to load hunt data'
  } finally {
    if (request === loadGeneration) loading.value = false
  }
}

const refreshData = async () => {
  await loadData()
}

const handleExecuteHunt = (hunt) => {
  if (!caseId.value) return
  huntSubmissionError.value = null
  selectedHunt.value = hunt
  showExecutionModal.value = true
}

const handleExecuteHuntSubmit = async (executionData) => {
  if (submittingHunt.value || !caseId.value) return
  const submittedCaseId = caseId.value
  const huntName = selectedHunt.value?.display_name
  submittingHunt.value = true
  huntSubmissionError.value = null
  try {
    const execution = await huntStore.executeHunt(
      executionData.huntId,
      submittedCaseId,
      executionData.parameters,
    )

    if (caseId.value !== submittedCaseId) return execution
    showNotification(`Hunt "${huntName}" started successfully`, 'success')

    // Switch to active executions tab
    activeTab.value = 'active'

    // Close modal
    showExecutionModal.value = false
    selectedHunt.value = null

    return execution
  } catch (err) {
    if (caseId.value !== submittedCaseId) return
    showNotification(err.message || 'Failed to execute hunt', 'error')
    huntSubmissionError.value = err.message || 'Failed to execute hunt'
  } finally {
    submittingHunt.value = false
  }
}

const handleExecutionModalCancel = () => {
  showExecutionModal.value = false
  selectedHunt.value = null
}

const handleViewHuntDetails = (hunt) => {
  selectedHunt.value = hunt
  showDetailsModal.value = true
}

const handleDetailsModalClose = () => {
  showDetailsModal.value = false
  // Don't clear selectedHunt if execution modal is open
  if (!showExecutionModal.value) {
    selectedHunt.value = null
  }
}

const handleCancelExecution = async (executionId) => {
  try {
    cancellingExecutions.value.add(executionId)

    await huntStore.cancelExecution(executionId)
    showNotification('Cancellation requested', 'info')
  } catch (err) {
    showNotification(err.message || 'Failed to cancel execution', 'error')
  } finally {
    cancellingExecutions.value.delete(executionId)
  }
}

const handleViewExecutionDetails = (executionId) => {
  const execution = huntStore.activeExecutions[executionId]
  if (execution) router.push(`/case/${execution.case_id}/hunts/execution/${executionId}`)
}

watch(
  caseId,
  () => {
    showExecutionModal.value = false
    showDetailsModal.value = false
    selectedHunt.value = null
    huntSubmissionError.value = null
    loadData()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  loadGeneration++
  huntStore.resetCaseExecutions()
})
</script>

<style scoped>
/* Any custom styles if needed */
</style>
