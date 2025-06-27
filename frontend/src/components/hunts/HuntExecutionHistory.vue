<template>
  <div class="hunt-execution-history">
    <!-- Search and Filter Bar -->
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" md="4">
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search executions..."
              variant="outlined"
              density="comfortable"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
              variant="outlined"
              density="comfortable"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="categoryFilter"
              :items="categoryOptions"
              label="Category"
              variant="outlined"
              density="comfortable"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-btn
              @click="clearFilters"
              variant="outlined"
              block
              :disabled="!hasActiveFilters"
            >
              Clear Filters
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Loading State -->
    <div v-if="loading" class="text-center pa-8">
      <v-progress-circular indeterminate size="64" />
      <div class="text-h6 mt-4">Loading execution history...</div>
    </div>

    <!-- Empty State -->
    <v-card v-else-if="filteredExecutions.length === 0" variant="outlined" class="text-center pa-8">
      <v-icon icon="mdi-history" size="64" color="grey" class="mb-4" />
      <div class="text-h6 mb-2">No executions found</div>
      <div class="text-body-2 text-medium-emphasis">
        {{ hasActiveFilters ? 'Try adjusting your search or filter criteria' : 'No hunt executions have been completed yet' }}
      </div>
    </v-card>

    <!-- Execution History Table -->
    <v-card v-else variant="outlined">
      <v-data-table
        :headers="headers"
        :items="filteredExecutions"
        :items-per-page="itemsPerPage"
        :items-per-page-options="[10, 25, 50, 100]"
        class="execution-history-table"
        item-value="id"
      >
        <!-- Hunt Name Column -->
        <template #item.hunt_display_name="{ item }">
          <div class="d-flex align-center">
            <v-avatar :color="getCategoryColor(item.hunt_category)" size="32" class="me-3">
              <v-icon :icon="getCategoryIcon(item.hunt_category)" color="white" size="small" />
            </v-avatar>
            <div>
              <div class="text-body-2 font-weight-medium">{{ item.hunt_display_name }}</div>
              <div class="text-caption text-medium-emphasis">{{ item.hunt_category }}</div>
            </div>
          </div>
        </template>

        <!-- Target Column -->
        <template #item.target="{ item }">
          <div class="text-body-2">
            {{ getTargetDisplay(item) }}
          </div>
        </template>

        <!-- Status Column -->
        <template #item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            :prepend-icon="getStatusIcon(item.status)"
            size="small"
            variant="flat"
          >
            {{ getStatusText(item.status) }}
          </v-chip>
        </template>

        <!-- Progress Column -->
        <template #item.progress="{ item }">
          <div class="d-flex align-center">
            <v-progress-linear
              :model-value="item.progress * 100"
              :color="getStatusColor(item.status)"
              height="6"
              rounded
              class="flex-grow-1 me-2"
              style="max-width: 100px;"
            />
            <span class="text-caption">{{ Math.round(item.progress * 100) }}%</span>
          </div>
        </template>

        <!-- Created At Column -->
        <template #item.created_at="{ item }">
          <div>
            <div class="text-body-2">{{ formatDate(item.created_at) }}</div>
            <div class="text-caption text-medium-emphasis">{{ formatTime(item.created_at) }}</div>
          </div>
        </template>

        <!-- Duration Column -->
        <template #item.duration="{ item }">
          <span class="text-body-2">{{ calculateDuration(item) }}</span>
        </template>

        <!-- Actions Column -->
        <template #item.actions="{ item }">
          <div class="d-flex align-center ga-1">
            <v-btn
              icon="mdi-eye"
              size="small"
              variant="text"
              @click="$emit('view-details', item.id)"
            />
            <v-btn
              v-if="item.status === 'completed' || item.status === 'partial'"
              icon="mdi-file-document"
              size="small"
              variant="text"
              @click="$emit('view-results', item.id)"
            />
            <v-menu>
              <template #activator="{ props }">
                <v-btn
                  icon="mdi-dots-vertical"
                  size="small"
                  variant="text"
                  v-bind="props"
                />
              </template>
              <v-list density="compact">
                <v-list-item
                  prepend-icon="mdi-eye"
                  title="View Details"
                  @click="$emit('view-details', item.id)"
                />
                <v-list-item
                  v-if="item.status === 'completed' || item.status === 'partial'"
                  prepend-icon="mdi-file-document"
                  title="View Results"
                  @click="$emit('view-results', item.id)"
                />
                <v-list-item
                  v-if="item.status === 'failed'"
                  prepend-icon="mdi-refresh"
                  title="Retry Execution"
                  @click="$emit('retry-execution', item)"
                />
              </v-list>
            </v-menu>
          </div>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getHuntTargetSummary } from '@/utils/huntDisplayUtils'

const props = defineProps({
  executions: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['view-details', 'view-results', 'retry-execution'])

// Local state
const searchQuery = ref('')
const statusFilter = ref(null)
const categoryFilter = ref(null)
const itemsPerPage = ref(25)

// Table headers
const headers = [
  { title: 'Hunt', key: 'hunt_display_name', sortable: true },
  { title: 'Target', key: 'target', sortable: true, width: 200 },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Progress', key: 'progress', sortable: true },
  { title: 'Started', key: 'created_at', sortable: true },
  { title: 'Duration', key: 'duration', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, width: 120 }
]

// Filter options
const statusOptions = [
  { title: 'Completed', value: 'completed' },
  { title: 'Failed', value: 'failed' },
  { title: 'Partial', value: 'partial' },
  { title: 'Cancelled', value: 'cancelled' },
  { title: 'Running', value: 'running' },
  { title: 'Pending', value: 'pending' }
]

const categoryOptions = computed(() => {
  const categories = [...new Set(props.executions.map(exec => exec.hunt_category).filter(Boolean))]
  return categories.map(category => ({
    title: category.charAt(0).toUpperCase() + category.slice(1),
    value: category
  }))
})

// Computed properties
const hasActiveFilters = computed(() => {
  return !!(searchQuery.value || statusFilter.value || categoryFilter.value)
})

const filteredExecutions = computed(() => {
  let filtered = props.executions

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(exec => {
      const target = getHuntTargetSummary(exec.initial_parameters || {}, exec.hunt_category || 'general')
      return exec.hunt_display_name?.toLowerCase().includes(query) ||
             exec.hunt_category?.toLowerCase().includes(query) ||
             exec.status.toLowerCase().includes(query) ||
             target.toLowerCase().includes(query)
    })
  }

  // Filter by status
  if (statusFilter.value) {
    filtered = filtered.filter(exec => exec.status === statusFilter.value)
  }

  // Filter by category
  if (categoryFilter.value) {
    filtered = filtered.filter(exec => exec.hunt_category === categoryFilter.value)
  }

  // Sort by created_at descending
  return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
})

// Methods
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

const getStatusIcon = (status) => {
  switch (status) {
    case 'pending': return 'mdi-clock-outline'
    case 'running': return 'mdi-play'
    case 'completed': return 'mdi-check'
    case 'partial': return 'mdi-alert'
    case 'failed': return 'mdi-close'
    case 'cancelled': return 'mdi-stop'
    default: return 'mdi-help'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'pending': return 'Pending'
    case 'running': return 'Running'
    case 'completed': return 'Completed'
    case 'partial': return 'Partial'
    case 'failed': return 'Failed'
    case 'cancelled': return 'Cancelled'
    default: return 'Unknown'
  }
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString()
}

const formatTime = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleTimeString()
}

const calculateDuration = (execution) => {
  if (!execution.started_at) return 'N/A'
  
  const startTime = new Date(execution.started_at)
  const endTime = execution.completed_at ? new Date(execution.completed_at) : new Date()
  const diffMs = endTime - startTime
  
  if (diffMs < 1000) return '< 1s'
  
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

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = null
  categoryFilter.value = null
}

const getTargetDisplay = (execution) => {
  const initialParams = execution.initial_parameters || {}
  const huntCategory = execution.hunt_category || 'general'
  
  return getHuntTargetSummary(initialParams, huntCategory)
}
</script>

<style scoped>
.execution-history-table :deep(.v-data-table__td) {
  padding: 8px 16px;
}

.execution-history-table :deep(.v-data-table__th) {
  padding: 8px 16px;
  font-weight: 600;
}
</style>