<template>
  <div>
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <div class="text-h6">Tasks</div>
        <div class="text-body-2 text-medium-emphasis">Manage tasks for this case</div>
      </div>
      <v-btn v-if="canCreateTasks" color="primary" @click="showCreateDialog = true">
        <v-icon start>mdi-plus</v-icon>
        New Task
      </v-btn>
    </div>

    <!-- Tasks Table -->
    <v-data-table :headers="headers" :items="tasks" :loading="loading" item-value="id">
      <!-- Title Column -->
      <template #[`item.title`]="{ item }">
        <router-link :to="`/tasks/${item.id}`" class="text-decoration-none">
          {{ item.title }}
        </router-link>
      </template>

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
        <v-btn
          :disabled="!canAssignTasks"
          icon
          size="small"
          variant="text"
          @click="openAssignDialog(item)"
        >
          <v-icon>mdi-account-plus</v-icon>
        </v-btn>
        <v-btn icon size="small" variant="text" @click="openStatusDialog(item)">
          <v-icon>mdi-progress-check</v-icon>
        </v-btn>
      </template>
    </v-data-table>

    <!-- Create Task Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <TaskForm :case-id="caseId" @cancel="showCreateDialog = false" @save="handleCreateTask" />
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useAuthStore } from '@/stores/auth'
import {
  TASK_PRIORITY_COLORS,
  TASK_PRIORITY_ICONS,
  TASK_PRIORITY_LABELS,
  TASK_STATUS,
  TASK_STATUS_COLORS,
  TASK_STATUS_LABELS,
} from '@/constants/tasks'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskAssignDialog from '@/components/tasks/TaskAssignDialog.vue'

const props = defineProps({
  caseId: {
    type: Number,
    required: true,
  },
})

const taskStore = useTaskStore()
const authStore = useAuthStore()

// Data
const showCreateDialog = ref(false)
const showAssignDialog = ref(false)
const showStatusDialog = ref(false)
const selectedTask = ref(null)
const newStatus = ref('')

// Computed
const loading = computed(() => taskStore.loading)
const tasks = computed(() => taskStore.tasks.filter((t) => t.case_id === props.caseId))

const canCreateTasks = computed(() => {
  // For now, show the create button for all non-analyst users
  // The backend will enforce the actual permission check
  return authStore.user?.role !== 'Analyst'
})

const canAssignTasks = computed(() => canCreateTasks.value)

const statusOptions = computed(() =>
  Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({ title, value })),
)

// Table configuration
const headers = [
  { title: 'Title', key: 'title', sortable: true },
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
  await taskStore.loadTasks({ case_id: props.caseId })
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

// Watch for case ID changes
watch(
  () => props.caseId,
  () => {
    loadTasks()
  },
)

// Lifecycle
onMounted(async () => {
  await loadTasks()
})
</script>
