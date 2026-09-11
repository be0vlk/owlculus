<template>
  <BaseDashboard title="Tasks">
    <v-alert v-if="usersError && !kind" type="error" class="mb-4">
      {{ usersError }}
      <v-btn :loading="usersLoading" @click="loadUsers">Retry users</v-btn>
    </v-alert>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
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
              aria-label="Refresh tasks"
              :disabled="pending"
              ref="refreshButton"
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
            <div class="text-headline-large font-weight-bold">{{ stats.total }}</div>
            <div class="text-body-medium text-medium-emphasis">Total Tasks</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-headline-large font-weight-bold text-primary">{{ stats.myTasks }}</div>
            <div class="text-body-medium text-medium-emphasis">My Tasks</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-headline-large font-weight-bold text-warning">{{ stats.overdue }}</div>
            <div class="text-body-medium text-medium-emphasis">Overdue</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card variant="outlined">
          <v-card-text class="text-center pa-4">
            <div class="text-headline-large font-weight-bold text-success">
              {{ stats.completed }}
            </div>
            <div class="text-body-medium text-medium-emphasis">Completed</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tasks Table Card -->
    <v-card variant="outlined">
      <!-- Header -->
      <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-format-list-checks" size="large" />
        <div class="flex-grow-1">
          <h2 class="text-title-large font-weight-bold">Task Management</h2>
          <div class="text-body-medium text-medium-emphasis">
            Track and manage tasks for the active case
          </div>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Filters and Search Toolbar -->
      <v-card-text class="pa-4">
        <v-row class="mb-0 align-center">
          <!-- Quick Filter Chips -->
          <v-col cols="12" md="8">
            <div class="d-flex align-center ga-2 flex-wrap">
              <span class="text-body-medium font-weight-medium me-2">Filter:</span>
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
                class="operations-search"
                variant="outlined"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />
      <TaskTable
        v-model="selected"
        :show-case="false"
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
        <span class="mr-3" role="status">{{ selected.length }} Tasks selected</span>
        <v-btn :disabled="!canAssign || pending" @click="openBulk('assign', $event)"
          >Bulk Assign</v-btn
        >
        <v-btn :disabled="!canUpdate || pending" class="ml-2" @click="openBulk('status', $event)"
          >Bulk Update Status</v-btn
        >
      </v-col>
    </v-row>

    <v-dialog
      :model-value="!!kind"
      :aria-label="kind === 'assign' ? 'Bulk Assign' : 'Bulk Update Status'"
      :persistent="pending"
      max-width="480"
      @update:model-value="
        (visible) => {
          if (!visible) close()
        }
      "
      @after-leave="restoreBulkFocus"
    >
      <v-card v-if="kind">
        <form @submit.prevent="submit">
          <v-card-title>{{
            kind === 'assign' ? 'Bulk Assign' : 'Bulk Update Status'
          }}</v-card-title>
          <v-card-text>
            <p class="mb-4">{{ targetedCount }} Tasks targeted</p>
            <v-alert v-if="feedback" type="warning" role="alert" class="mb-4">{{
              feedback
            }}</v-alert>
            <v-alert v-if="kind === 'assign' && usersError" type="error" class="mb-4">
              {{ usersError }}
              <v-btn :loading="usersLoading" @click="loadUsers">Retry users</v-btn>
            </v-alert>
            <v-select
              v-model="value"
              :items="kind === 'assign' ? assigneeOptions : statusOptions"
              :label="kind === 'assign' ? 'Assign To' : 'New Status'"
              :disabled="pending || (kind === 'assign' && (usersLoading || !!usersError))"
              :loading="kind === 'assign' && usersLoading"
            />
            <p v-if="pending" role="status">Applying Task updates…</p>
            <v-btn v-if="needsRefresh" :disabled="pending" @click="refresh">Refresh Tasks</v-btn>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn :disabled="pending" @click="close">Cancel</v-btn>
            <v-btn type="submit" color="primary" :disabled="!canSubmit" :loading="pending"
              >Apply</v-btn
            >
          </v-card-actions>
        </form>
      </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="snackbar.timeout">
      {{ snackbar.text }}
      <template #actions><v-btn @click="snackbar.show = false">Close</v-btn></template>
    </v-snackbar>

    <!-- Create Task Dialog -->
    <v-dialog aria-label="Create Task" v-model="showCreateDialog" max-width="600">
      <TaskForm :saving="loading" @cancel="showCreateDialog = false" @save="handleCreateTask" />
    </v-dialog>
  </BaseDashboard>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useBulkTaskActions } from '@/composables/useBulkTaskActions'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useTaskStore } from '@/stores/taskStore'
import { useAuthStore } from '@/stores/auth'
import { useTaskTable } from '@/composables/useTaskTable'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskTable from '@/components/tasks/TaskTable.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'

const taskStore = useTaskStore()
const authStore = useAuthStore()
const { canCreateTasks } = useTaskTable()

// Data
const showCreateDialog = ref(false)
const context = useActiveCaseStore()
const refreshButton = ref(null)
let bulkActivator
let bulkCaseId
const searchQuery = ref('')
const activeQuickFilter = ref('me')

// Computed
const loading = computed(() => taskStore.loading)
const error = computed(() => taskStore.error)
const stats = computed(() => taskStore.stats)

const filteredAndSearchedTasks = computed(() => {
  let result = taskStore.filteredTasks.filter((task) => task.case_id === context.activeCaseId)

  // Apply quick filter
  if (activeQuickFilter.value === 'me' && authStore.user) {
    result = result.filter((task) => task.assigned_to?.id === authStore.user.id)
  }

  // Apply search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(
      (task) =>
        task.title.toLowerCase().includes(query) ||
        (task.description || '').toLowerCase().includes(query),
    )
  }

  return result
})

const {
  selected,
  targetedCount,
  kind,
  value,
  pending,
  feedback,
  usersLoading,
  usersError,
  needsRefresh,
  canAssign,
  canUpdate,
  canSubmit,
  assigneeOptions,
  statusOptions,
  snackbar,
  open,
  close,
  submit,
  loadUsers,
  refresh,
} = useBulkTaskActions(filteredAndSearchedTasks)

function openBulk(action, event) {
  bulkCaseId = context.activeCaseId
  bulkActivator = event.currentTarget
  open(action)
}

function restoreBulkFocus() {
  if (kind.value || bulkCaseId !== context.activeCaseId) return
  const target =
    bulkActivator?.isConnected && !bulkActivator.disabled ? bulkActivator : refreshButton.value?.$el
  target?.focus()
}

// Methods
async function loadTasks() {
  await taskStore.loadTasks()
}

async function handleCreateTask(taskData) {
  if (loading.value) return
  try {
    await taskStore.createTask(taskData)
    showCreateDialog.value = false
    await loadTasks()
  } catch (error) {
    console.error('Failed to create task:', error)
    // Dialog remains open on error
  }
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
    return 'Get started by creating your first task to track work in this case.'
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
