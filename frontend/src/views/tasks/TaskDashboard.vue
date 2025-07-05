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
      <v-data-table
        v-model="selected"
        :headers="headers"
        :items="filteredAndSearchedTasks"
        :loading="loading"
        class="tasks-dashboard-table"
        hover
        item-value="id"
        show-select
        @click:row="handleRowClick"
      >
        <!-- Title Column -->
        <template #[`item.title`]="{ item }">
          {{ item.title }}
        </template>

        <!-- Case Column -->
        <template #[`item.case`]="{ item }"> Case #{{ item.case_id }} </template>

        <!-- Priority Column -->
        <template #[`item.priority`]="{ item }">
          <v-chip :color="TASK_PRIORITY_COLORS[item.priority]" size="small">
            <v-icon size="small" start>{{ TASK_PRIORITY_ICONS[item.priority] }}</v-icon>
            {{ TASK_PRIORITY_LABELS[item.priority] }}
          </v-chip>
        </template>

        <!-- Status Column -->
        <template #[`item.status`]="{ item }">
          <v-chip :color="TASK_STATUS_COLORS[item.status]" size="small">
            {{ TASK_STATUS_LABELS[item.status] }}
          </v-chip>
        </template>

        <!-- Assignee Column -->
        <template #[`item.assignee`]="{ item }">
          <span v-if="item.assigned_to">
            {{ item.assigned_to.username }}
          </span>
          <span v-else class="text-grey"> Unassigned </span>
        </template>

        <!-- Due Date Column -->
        <template #[`item.due_date`]="{ item }">
          <span v-if="item.due_date" :class="{ 'text-error': isOverdue(item) }">
            {{ formatDate(item.due_date) }}
          </span>
        </template>

        <!-- Actions Column -->
        <template #[`item.actions`]="{ item }">
          <div class="d-flex ga-1">
            <v-btn
              :disabled="!canAssignTasks"
              icon
              size="small"
              variant="text"
              @click="openAssignDialog(item)"
            >
              <v-icon>mdi-account-plus</v-icon>
              <v-tooltip activator="parent" location="top">Assign Task</v-tooltip>
            </v-btn>
            <v-btn icon size="small" variant="text" @click="openStatusDialog(item)">
              <v-icon>mdi-progress-check</v-icon>
              <v-tooltip activator="parent" location="top">Update Status</v-tooltip>
            </v-btn>
          </div>
        </template>

        <!-- Empty state -->
        <template #no-data>
          <div class="text-center pa-12">
            <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-format-list-checks" size="64" />
            <h3 class="text-h6 font-weight-medium mb-2">
              {{ getEmptyStateTitle() }}
            </h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              {{ getEmptyStateMessage() }}
            </p>
            <v-btn
              v-if="shouldShowCreateButton()"
              :disabled="!canCreateTasks"
              color="primary"
              prepend-icon="mdi-plus"
              @click="showCreateDialog = true"
            >
              Create First Task
            </v-btn>
          </div>
        </template>
      </v-data-table>
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

    <!-- Assign Dialog -->
    <v-dialog v-model="showAssignDialog" max-width="400">
      <TaskAssignDialog
        v-if="selectedTask"
        :task="selectedTask"
        @assign="handleAssign"
        @cancel="showAssignDialog = false"
      />
    </v-dialog>

    <!-- Status Dialog -->
    <v-dialog v-model="showStatusDialog" max-width="400">
      <v-card v-if="selectedTask">
        <v-card-title>Update Status</v-card-title>
        <v-card-text>
          <v-select v-model="newStatus" :items="statusOptions" label="New Status" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showStatusDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="handleStatusUpdate">Update</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </BaseDashboard>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { useAuthStore } from '@/stores/auth'
import {
  TASK_STATUS,
  TASK_STATUS_LABELS,
  TASK_STATUS_COLORS,
  TASK_PRIORITY_LABELS,
  TASK_PRIORITY_COLORS,
  TASK_PRIORITY_ICONS,
} from '@/constants/tasks'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskAssignDialog from '@/components/tasks/TaskAssignDialog.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'

const taskStore = useTaskStore()
const authStore = useAuthStore()
const router = useRouter()

// Data
const showCreateDialog = ref(false)
const showAssignDialog = ref(false)
const showStatusDialog = ref(false)
const selectedTask = ref(null)
const newStatus = ref('')
const selected = ref([])
const searchQuery = ref('')
const activeQuickFilter = ref('me')

// Computed
const loading = computed(() => taskStore.loading)
const error = computed(() => taskStore.error)
const stats = computed(() => taskStore.stats)

const canCreateTasks = computed(() => {
  // Show for non-analyst users; backend will enforce actual permissions
  return authStore.user?.role !== 'Analyst'
})

const canAssignTasks = computed(() => {
  // Show for non-analyst users; backend will enforce actual permissions
  return authStore.user?.role !== 'Analyst'
})

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

// Status options for the status update dialog
const statusOptions = computed(() =>
  Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({ title, value })),
)

// Table configuration
const headers = [
  { title: 'Title', key: 'title', sortable: true },
  { title: 'Case', key: 'case', sortable: true },
  { title: 'Priority', key: 'priority', sortable: true },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Assignee', key: 'assignee', sortable: true },
  { title: 'Due Date', key: 'due_date', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false },
]

// Methods
function formatDate(date) {
  if (!date) return ''
  return new Date(date).toLocaleDateString()
}

function isOverdue(task) {
  if (!task.due_date || task.status === TASK_STATUS.COMPLETED) return false
  return new Date(task.due_date) < new Date()
}

async function loadTasks() {
  await taskStore.loadTasks()
}

async function handleCreateTask(taskData) {
  await taskStore.createTask(taskData)
  showCreateDialog.value = false
  await loadTasks()
}

function openAssignDialog(task) {
  selectedTask.value = task
  showAssignDialog.value = true
}

function openStatusDialog(task) {
  selectedTask.value = task
  newStatus.value = task.status
  showStatusDialog.value = true
}

async function handleAssign(userId) {
  await taskStore.assignTask(selectedTask.value.id, userId)
  showAssignDialog.value = false
  selectedTask.value = null
}

async function handleStatusUpdate() {
  await taskStore.updateTaskStatus(selectedTask.value.id, newStatus.value)
  showStatusDialog.value = false
  selectedTask.value = null
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

function handleRowClick(event, { item }) {
  router.push(`/tasks/${item.id}`)
}

// Lifecycle
onMounted(async () => {
  // Load tasks without any filters
  try {
    await loadTasks()
    // We no longer need to load users since we're not using assignee dropdown
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>

<style scoped>
.tasks-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.tasks-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.tasks-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}

.tasks-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>
