<template>
  <BaseDashboard :error="error" :loading="loading" title="Tasks">
    <template #header-actions>
      <div class="d-flex align-center ga-2">
        <v-btn
          :disabled="!canCreateTasks"
          color="white"
          prepend-icon="mdi-plus"
          variant="text"
          @click="showCreateDialog = true"
        >
          New Task
        </v-btn>
        <v-tooltip location="bottom" text="Refresh tasks">
          <template #activator="{ props }">
            <v-btn
              :loading="loading"
              icon="mdi-refresh"
              v-bind="props"
              variant="outlined"
              @click="loadTasks"
            />
          </template>
        </v-tooltip>
      </div>
    </template>

    <!-- Stats Cards -->
    <v-row class="mb-4">
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-h4 font-weight-bold">{{ stats.total }}</div>
            <div class="text-body-2 text-medium-emphasis">Total Tasks</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-h4 font-weight-bold text-primary">{{ stats.myTasks }}</div>
            <div class="text-body-2 text-medium-emphasis">My Tasks</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-h4 font-weight-bold text-warning">{{ stats.overdue }}</div>
            <div class="text-body-2 text-medium-emphasis">Overdue</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-h4 font-weight-bold text-success">{{ stats.completed }}</div>
            <div class="text-body-2 text-medium-emphasis">Completed</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tasks Table Card -->
    <v-card variant="outlined">
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-format-list-checks" size="large" />
        <div class="flex-grow-1">
          <div class="text-h6 font-weight-bold">Task Management</div>
          <div class="text-body-2 text-medium-emphasis">
            Track and manage tasks across all cases
          </div>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Filters and Search Toolbar -->
      <v-card-text class="pa-4">
        <v-row align="center" class="mb-0">
          <!-- Quick Filter Chips -->
          <v-col cols="12" md="8">
            <div class="d-flex align-center ga-2 flex-wrap">
              <span class="text-body-2 font-weight-medium me-2">Filter:</span>
              <v-chip-group
                v-model="activeQuickFilter"
                color="primary"
                selected-class="text-primary"
                variant="outlined"
              >
                <v-chip filter size="small" value="all"> All Tasks </v-chip>
                <v-chip filter size="small" value="me"> My Tasks </v-chip>
              </v-chip-group>
            </div>
          </v-col>

          <!-- Search Field -->
          <v-col cols="12" md="4">
            <div class="d-flex align-center ga-2 justify-end">
              <v-text-field
                v-model="searchQuery"
                clearable
                density="comfortable"
                hide-details
                label="Search tasks..."
                prepend-inner-icon="mdi-magnify"
                style="min-width: 200px; max-width: 280px"
                variant="outlined"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />
      <TaskTable
        v-model="selected"
        :show-case="true"
        :loading="loading"
        :show-select="true"
        :tasks="filteredAndSearchedTasks"
      >
        <template #empty-title>{{ getEmptyStateTitle() }}</template>
        <template #empty-message>{{ getEmptyStateMessage() }}</template>
        <template #empty-action>
          <v-btn
            v-if="shouldShowCreateButton()"
            :disabled="!canCreateTasks"
            color="primary"
            prepend-icon="mdi-plus"
            @click="showCreateDialog = true"
          >
            Create First Task
          </v-btn>
        </template>
      </TaskTable>
    </v-card>

    <!-- Bulk Actions -->
    <v-row v-if="selected.length > 0" class="mt-4">
      <v-col>
        <v-btn :disabled="!canAssignTasks" @click="bulkAssign"> Bulk Assign </v-btn>
        <v-btn class="ml-2" @click="bulkUpdateStatus"> Bulk Update Status </v-btn>
      </v-col>
    </v-row>

    <!-- Create Task Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <TaskForm @cancel="showCreateDialog = false" @save="handleCreateTask" />
    </v-dialog>
  </BaseDashboard>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue'
import {useTaskStore} from '@/stores/taskStore'
import {useAuthStore} from '@/stores/auth'
import {useTaskTable} from '@/composables/useTaskTable'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskTable from '@/components/tasks/TaskTable.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'

const taskStore = useTaskStore()
const authStore = useAuthStore()
const { canCreateTasks, canAssignTasks } = useTaskTable()

// Data
const showCreateDialog = ref(false)
const selected = ref([])
const searchQuery = ref('')
const activeQuickFilter = ref('me')

// Computed
const loading = computed(() => taskStore.loading)
const error = computed(() => taskStore.error)
const stats = computed(() => taskStore.stats)

const filteredAndSearchedTasks = computed(() => {
  let result = taskStore.tasks || []

  // Apply quick filter
  if (activeQuickFilter.value === 'me' && authStore.user) {
    result = result.filter((task) => task.assigned_to?.id === authStore.user.id)
  }

  // Apply search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(
      (task) =>
        task.title.toLowerCase().includes(query) || task.description.toLowerCase().includes(query),
    )
  }

  return result
})

// Methods
async function loadTasks() {
  await taskStore.loadTasks()
}

async function handleCreateTask(taskData) {
  try {
    await taskStore.createTask(taskData)
    showCreateDialog.value = false
    await loadTasks()
  } catch (error) {
    console.error('Failed to create task:', error)
    // Dialog remains open on error
  }
}

async function bulkAssign() {
  // TODO: Implement bulk assign dialog
  console.log('Bulk assign:', selected.value)
}

async function bulkUpdateStatus() {
  // TODO: Implement bulk status update dialog
  console.log('Bulk update status:', selected.value)
}

// Empty state helper functions
const getEmptyStateTitle = () => {
  if (searchQuery.value) {
    return 'No tasks found'
  } else if (activeQuickFilter.value === 'me') {
    return 'No tasks assigned to you'
  } else {
    return 'No tasks yet'
  }
}

const getEmptyStateMessage = () => {
  if (searchQuery.value) {
    return "Try adjusting your search terms to find the task you're looking for."
  } else if (activeQuickFilter.value === 'me') {
    return "You don't have any tasks assigned. Check 'All Tasks' to see unassigned tasks."
  } else {
    return 'Get started by creating your first task to track work across cases.'
  }
}

const shouldShowCreateButton = () => {
  return !searchQuery.value && activeQuickFilter.value === 'all' && canCreateTasks.value
}

// Lifecycle
onMounted(async () => {
  try {
    await loadTasks()
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>
