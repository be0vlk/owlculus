<template>
  <BaseDashboard
    title="Hunt Management"
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
          @click="refreshData"
          :loading="loading"
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

    <!-- Main Content -->
    <v-card variant="outlined">
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
          <v-chip v-if="huntStore.runningExecutions.length > 0" size="small" color="primary" class="ml-2">
            {{ huntStore.runningExecutions.length }}
          </v-chip>
        </v-tab>
        <v-tab value="history" prepend-icon="mdi-history">
          Execution History
        </v-tab>
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
              <div class="text-h6 mb-4">Running Executions</div>
              <v-row>
                <v-col
                  v-for="execution in huntStore.runningExecutions"
                  :key="`running-${execution.id}`"
                  cols="12"
                  md="6"
                  lg="4"
                >
                  <HuntProgressCard
                    :execution="execution"
                    :cancelling="cancellingExecutions.has(execution.id)"
                    @cancel="handleCancelExecution"
                    @view-details="handleViewExecutionDetails"
                    @view-results="handleViewExecutionResults"
                  />
                </v-col>
              </v-row>
            </div>

            <!-- Recently Completed -->
            <div v-if="huntStore.completedExecutions.length > 0" class="mt-6">
              <div class="text-h6 mb-4">Recently Completed</div>
              <v-row>
                <v-col
                  v-for="execution in huntStore.completedExecutions.slice(0, 6)"
                  :key="`completed-${execution.id}`"
                  cols="12"
                  md="6"
                  lg="4"
                >
                  <HuntProgressCard
                    :execution="execution"
                    @view-details="handleViewExecutionDetails"
                    @view-results="handleViewExecutionResults"
                  />
                </v-col>
              </v-row>
            </div>

            <!-- Empty State -->
            <div v-if="huntStore.runningExecutions.length === 0 && huntStore.completedExecutions.length === 0" class="text-center pa-8">
              <v-icon icon="mdi-play-circle-outline" size="64" color="grey" class="mb-4" />
              <div class="text-h6 mb-2">No Active Executions</div>
              <div class="text-body-2 text-medium-emphasis mb-4">
                Start a hunt from the Available Hunts tab to begin investigating
              </div>
              <v-btn color="primary" @click="activeTab = 'catalog'">
                Browse Hunts
              </v-btn>
            </div>
          </div>
        </v-tabs-window-item>

        <!-- Execution History Tab -->
        <v-tabs-window-item value="history">
          <div class="pa-4">
            <HuntExecutionHistory
              :executions="huntStore.executionHistory.filter(exec => exec.status !== 'running' && exec.status !== 'pending')"
              :loading="historyLoading"
              @view-details="handleViewExecutionDetails"
              @view-results="handleViewExecutionResults"
              @retry-execution="handleRetryExecution"
            />
          </div>
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card>

    <!-- Hunt Execution Modal -->
    <HuntExecutionModal
      v-model="showExecutionModal"
      :hunt="selectedHunt"
      :cases="cases"
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
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useHuntStore } from '@/stores/hunt'
import { useNotifications } from '@/composables/useNotifications'
import BaseDashboard from '@/components/BaseDashboard.vue'
import HuntCatalog from '@/components/hunts/HuntCatalog.vue'
import HuntProgressCard from '@/components/hunts/HuntProgressCard.vue'
import HuntExecutionModal from '@/components/hunts/HuntExecutionModal.vue'
import HuntDetailsModal from '@/components/hunts/HuntDetailsModal.vue'
import HuntExecutionHistory from '@/components/hunts/HuntExecutionHistory.vue'
import { caseService } from '@/services/case'

// Store and router
const router = useRouter()
const authStore = useAuthStore()
const huntStore = useHuntStore()
const { showNotification } = useNotifications()

// Local state
const loading = ref(true)
const historyLoading = ref(false)
const error = ref(null)
const activeTab = ref('catalog')
const selectedHunt = ref(null)
const showExecutionModal = ref(false)
const showDetailsModal = ref(false)
const cases = ref([])
const cancellingExecutions = ref(new Set())

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
  try {
    loading.value = true
    error.value = null
    
    // Load hunts and cases first
    await Promise.all([
      huntStore.fetchHunts(),
      loadCases()
    ])
    
    // Then load active executions from all accessible cases
    await huntStore.loadAllActiveExecutions(cases.value)
  } catch (err) {
    error.value = err.message || 'Failed to load hunt data'
    console.error('Failed to load hunt data:', err)
  } finally {
    loading.value = false
  }
}

const loadCases = async () => {
  try {
    const response = await caseService.getCases()
    cases.value = response || []
  } catch (err) {
    console.error('Failed to load cases:', err)
    // Don't set error here as it's not critical for hunt management
  }
}

const refreshData = async () => {
  await loadData()
}

const handleExecuteHunt = (hunt) => {
  selectedHunt.value = hunt
  showExecutionModal.value = true
}

const handleExecuteHuntSubmit = async (executionData) => {
  try {
    const execution = await huntStore.executeHunt(
      executionData.huntId,
      executionData.caseId,
      executionData.parameters
    )
    
    showNotification(`Hunt "${selectedHunt.value.display_name}" started successfully`, 'success')
    
    // Switch to active executions tab
    activeTab.value = 'active'
    
    // Close modal
    showExecutionModal.value = false
    selectedHunt.value = null
    
    return execution
  } catch (err) {
    showNotification(err.message || 'Failed to execute hunt', 'error')
    throw err
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
  selectedHunt.value = null
}

const handleCancelExecution = async (executionId) => {
  try {
    cancellingExecutions.value.add(executionId)
    
    await huntStore.cancelExecution(executionId)
    showNotification('Hunt execution cancelled', 'info')
  } catch (err) {
    showNotification(err.message || 'Failed to cancel execution', 'error')
  } finally {
    cancellingExecutions.value.delete(executionId)
  }
}

const handleViewExecutionDetails = (executionId) => {
  router.push(`/hunts/execution/${executionId}`)
}

const handleViewExecutionResults = (executionId) => {
  router.push(`/hunts/execution/${executionId}/results`)
}

const handleRetryExecution = async (execution) => {
  // Pre-populate modal with previous execution data
  selectedHunt.value = execution.hunt
  showExecutionModal.value = true
}

// Lifecycle
onMounted(async () => {
  if (!checkAccess()) return
  
  await loadData()
})

onUnmounted(() => {
  // Cleanup WebSocket connections
  huntStore.cleanup()
})
</script>

<style scoped>
/* Any custom styles if needed */
</style>