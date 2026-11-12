<template>
  <div class="hunt-execution-history">
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-row class="align-center">
          <v-col cols="12" md="4">
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search executions..."
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="statusFilter"
              :items="statusOptions"
              label="Status"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="categoryFilter"
              :items="categoryOptions"
              label="Category"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-btn :disabled="!hasActiveFilters" block variant="outlined" @click="clearFilters">
              Clear Filters
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <div v-if="loading" class="text-center pa-8">
      <v-progress-circular indeterminate size="64" />
      <div class="text-title-large mt-4">Loading execution history...</div>
    </div>

    <v-card v-else-if="filteredExecutions.length === 0" variant="outlined" class="text-center pa-8">
      <v-icon icon="mdi-history" size="64" color="grey" class="mb-4" />
      <div class="text-title-large mb-2">No executions found</div>
      <div class="text-body-medium text-medium-emphasis">
        {{
          hasActiveFilters
            ? 'Try adjusting your search or filter criteria'
            : 'No hunt executions have been completed yet'
        }}
      </div>
    </v-card>

    <v-card v-else variant="outlined">
      <v-data-table
        :headers="headers"
        :items="filteredExecutions"
        :items-per-page="itemsPerPage"
        :items-per-page-options="[10, 25, 50, 100]"
        :sort-by="[{ key: 'created_at', order: 'desc' }]"
        density="comfortable"
        item-value="id"
      >
        <template #[`item.hunt_display_name`]="{ item }">
          <div class="d-flex align-center">
            <v-avatar
              :color="getCategoryColor(item.hunt_category)"
              class="me-3"
              size="32"
              variant="tonal"
            >
              <v-icon :icon="getCategoryIcon(item.hunt_category)" size="small" />
            </v-avatar>
            <div class="text-body-medium font-weight-medium">{{ item.hunt_display_name }}</div>
          </div>
        </template>

        <template #[`item.target`]="{ item }">
          <div class="text-body-medium">
            {{ getTargetDisplay(item) }}
          </div>
        </template>

        <template #[`item.status`]="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            :prepend-icon="getStatusIcon(item.status)"
            size="small"
            variant="tonal"
          >
            {{ getStatusText(item.status) }}
          </v-chip>
        </template>

        <template #[`item.progress`]="{ item }">
          <div class="d-flex align-center">
            <v-progress-linear
              :model-value="item.progress * 100"
              :color="getStatusColor(item.status)"
              height="6"
              rounded
              class="flex-grow-1 me-2"
              style="max-width: 100px"
            />
            <span class="text-body-small">{{ Math.round(item.progress * 100) }}%</span>
          </div>
        </template>

        <template #[`item.created_at`]="{ item }">
          <div class="text-body-medium">{{ formatDate(item.created_at) }}</div>
        </template>

        <template #[`item.duration`]="{ item }">
          <span class="text-body-medium">{{
            calculateDuration(item.started_at, item.completed_at)
          }}</span>
        </template>

        <template #[`item.actions`]="{ item }">
          <v-btn
            icon="mdi-eye"
            :aria-label="`View ${item.hunt_display_name} execution`"
            size="small"
            variant="text"
            @click="$emit('view-details', item.id)"
          />
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  calculateDuration,
  getHuntTargetSummary,
  getCategoryColor,
  getCategoryIcon,
  getStatusColor,
  getStatusIcon,
  getStatusText as formatStatusText,
} from '@/utils/huntDisplayUtils'
import { formatDate } from '@/composables/dateUtils'

const props = defineProps({
  executions: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['view-details'])

const searchQuery = ref('')
const statusFilter = ref(null)
const categoryFilter = ref(null)
const itemsPerPage = ref(25)

const headers = [
  { title: 'Hunt', key: 'hunt_display_name', sortable: true },
  { title: 'Target', key: 'target', sortable: true, width: 200 },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Progress', key: 'progress', sortable: true },
  { title: 'Started', key: 'created_at', sortable: true },
  { title: 'Duration', key: 'duration', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, width: 80 },
]

const statusOptions = ['completed', 'failed', 'partial', 'cancelled', 'running', 'pending'].map(
  (value) => ({ title: formatStatusText(value, true), value }),
)

const categoryOptions = computed(() => {
  const categories = [
    ...new Set(props.executions.map((exec) => exec.hunt_category).filter(Boolean)),
  ]
  return categories.map((category) => ({
    title: category.charAt(0).toUpperCase() + category.slice(1),
    value: category,
  }))
})

const hasActiveFilters = computed(() => {
  return !!(searchQuery.value || statusFilter.value || categoryFilter.value)
})

const filteredExecutions = computed(() => {
  let filtered = props.executions

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter((exec) => {
      const target = getHuntTargetSummary(
        exec.initial_parameters || {},
        exec.hunt_category || 'general',
      )
      return (
        exec.hunt_display_name?.toLowerCase().includes(query) ||
        exec.hunt_category?.toLowerCase().includes(query) ||
        exec.status.toLowerCase().includes(query) ||
        target.toLowerCase().includes(query)
      )
    })
  }

  if (statusFilter.value) {
    filtered = filtered.filter((exec) => exec.status === statusFilter.value)
  }

  if (categoryFilter.value) {
    filtered = filtered.filter((exec) => exec.hunt_category === categoryFilter.value)
  }

  return filtered.map((exec) => ({
    ...exec,
    target: getTargetDisplay(exec),
  }))
})

const getStatusText = (status) => formatStatusText(status, true)

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = null
  categoryFilter.value = null
}

const getTargetDisplay = (execution) =>
  getHuntTargetSummary(execution.initial_parameters || {}, execution.hunt_category || 'general')
</script>
