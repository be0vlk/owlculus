<template>
  <v-container v-if="task">
    <!-- Header -->
    <v-row align="center" class="mb-4">
      <v-col cols="auto">
        <v-btn icon variant="text" @click="$router.back()">
          <v-icon>mdi-arrow-left</v-icon>
        </v-btn>
      </v-col>
      <v-col>
        <h1 class="text-h4">{{ task.title }}</h1>
      </v-col>
      <v-col cols="auto">
        <v-btn v-if="canEditTask" @click="editMode = true">
          <v-icon start>mdi-pencil</v-icon>
          Edit
        </v-btn>
      </v-col>
    </v-row>

    <!-- Task Details Card -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="8">
            <div class="text-h6 mb-2">Description</div>
            <p>{{ task.description }}</p>
          </v-col>
          <v-col cols="12" md="4">
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>Status</v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip
                    :color="TASK_STATUS_COLORS[task.status]"
                    size="small"
                    @click="canEditTask && openStatusDialog()"
                  >
                    {{ TASK_STATUS_LABELS[task.status] }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <v-list-item-title>Priority</v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip :color="TASK_PRIORITY_COLORS[task.priority]" size="small">
                    <v-icon size="small" start>{{ TASK_PRIORITY_ICONS[task.priority] }}</v-icon>
                    {{ TASK_PRIORITY_LABELS[task.priority] }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <v-list-item-title>Assigned To</v-list-item-title>
                <v-list-item-subtitle>
                  <span v-if="task.assigned_to">
                    {{ task.assigned_to.username }}
                  </span>
                  <span v-else class="text-grey"> Unassigned </span>
                  <v-btn
                    v-if="canAssignTask"
                    class="ml-2"
                    icon
                    size="x-small"
                    variant="text"
                    @click="openAssignDialog"
                  >
                    <v-icon>mdi-pencil</v-icon>
                  </v-btn>
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <v-list-item-title>Case</v-list-item-title>
                <v-list-item-subtitle>
                  <router-link :to="`/case/${task.case_id}`" class="text-decoration-none">
                    Case #{{ task.case_id }}
                  </router-link>
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item v-if="task.due_date">
                <v-list-item-title>Due Date</v-list-item-title>
                <v-list-item-subtitle :class="{ 'text-error': isOverdue }">
                  {{ formatDate(task.due_date) }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <v-list-item-title>Created</v-list-item-title>
                <v-list-item-subtitle>
                  {{ formatDateTime(task.created_at) }} by {{ task.assigned_by.username }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item v-if="task.completed_at">
                <v-list-item-title>Completed</v-list-item-title>
                <v-list-item-subtitle>
                  {{ formatDateTime(task.completed_at) }} by {{ task.completed_by?.username }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Edit Dialog -->
    <v-dialog v-model="editMode" max-width="600">
      <TaskForm :task="task" @cancel="editMode = false" @save="handleUpdate" />
    </v-dialog>

    <!-- Assign Dialog -->
    <v-dialog v-model="showAssignDialog" max-width="400">
      <TaskAssignDialog :task="task" @assign="handleAssign" @cancel="showAssignDialog = false" />
    </v-dialog>

    <!-- Status Dialog -->
    <v-dialog v-model="showStatusDialog" max-width="400">
      <v-card>
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
  </v-container>

  <!-- Loading State -->
  <v-container v-else-if="loading" class="text-center">
    <v-progress-circular indeterminate />
  </v-container>

  <!-- Error State -->
  <v-container v-else class="text-center">
    <v-alert type="error"> Task not found </v-alert>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { useAuthStore } from '@/stores/auth'
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_COLORS,
  TASK_PRIORITY_LABELS,
  TASK_PRIORITY_COLORS,
  TASK_PRIORITY_ICONS,
} from '@/constants/tasks'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskAssignDialog from '@/components/tasks/TaskAssignDialog.vue'

const route = useRoute()
const taskStore = useTaskStore()
const authStore = useAuthStore()

// Data
const editMode = ref(false)
const showAssignDialog = ref(false)
const showStatusDialog = ref(false)
const newStatus = ref('')

// Computed
const taskId = computed(() => parseInt(route.params.id))
const task = computed(() => taskStore.currentTask)
const loading = computed(() => taskStore.loading)

const canEditTask = computed(() => {
  if (!task.value) return false
  // Admin or case lead can edit
  return authStore.isAdmin || authStore.user?.is_lead
})

const canAssignTask = computed(() => {
  return canEditTask.value
})

const isOverdue = computed(() => {
  if (!task.value?.due_date || task.value.status === 'completed') return false
  return new Date(task.value.due_date) < new Date()
})

const statusOptions = computed(() =>
  Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({ title, value })),
)

// Methods
function formatDate(date) {
  return new Date(date).toLocaleDateString()
}

function formatDateTime(date) {
  return new Date(date).toLocaleString()
}

function openAssignDialog() {
  showAssignDialog.value = true
}

function openStatusDialog() {
  newStatus.value = task.value.status
  showStatusDialog.value = true
}

async function handleUpdate(updates) {
  await taskStore.updateTask(taskId.value, updates)
  editMode.value = false
}

async function handleAssign(userId) {
  await taskStore.assignTask(taskId.value, userId)
  showAssignDialog.value = false
}

async function handleStatusUpdate() {
  await taskStore.updateTaskStatus(taskId.value, newStatus.value)
  showStatusDialog.value = false
}

// Lifecycle
onMounted(async () => {
  await taskStore.loadTask(taskId.value)
})
</script>
