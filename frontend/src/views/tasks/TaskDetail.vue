<template>
  <BaseDashboard
    :loading="loading"
    :error="error"
    :title="task ? `Task: ${task.title}` : 'Task Details'"
    :show-sidebar="true"
  >
    <template #header-actions>
      <div v-if="task" class="d-flex align-center ga-2">
        <v-btn color="white" prepend-icon="mdi-arrow-left" variant="text" @click="$router.back()">
          Back
        </v-btn>
        <v-btn
          v-if="canEditFull"
          color="white"
          prepend-icon="mdi-pencil"
          variant="text"
          @click="editMode = true"
        >
          Edit Task
        </v-btn>
        <v-btn
          v-else-if="canEditLimited"
          color="white"
          prepend-icon="mdi-pencil-box-outline"
          variant="text"
          @click="showQuickEditDialog = true"
        >
          Quick Edit
        </v-btn>
      </div>
    </template>

    <template #loading>
      <v-card variant="outlined" class="pa-8 mx-auto" max-width="400">
        <v-progress-circular
          size="64"
          width="4"
          color="primary"
          indeterminate
          class="mb-4 d-block mx-auto"
        />
        <div class="text-h6 text-center">Loading task...</div>
        <div class="text-body-2 text-medium-emphasis text-center">
          Please wait while we load the task details
        </div>
      </v-card>
    </template>

    <!-- Task Content -->
    <div v-if="task">
      <!-- Task Information Card -->
      <v-card variant="outlined">
        <!-- Header -->
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-icon icon="mdi-checkbox-marked-circle" color="primary" size="large" class="me-3" />
          <div class="flex-grow-1">
            <div class="text-h6 font-weight-bold">Task Information</div>
            <div class="text-body-2 text-medium-emphasis">Details and metadata for this task</div>
          </div>
          <v-chip
            :color="isEditing ? 'warning' : 'primary'"
            size="small"
            variant="tonal"
            class="me-3"
          >
            {{ isEditing ? 'Editing' : 'View Mode' }}
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-6">
          <v-row>
            <v-col cols="12" lg="8">
              <div class="mb-6">
                <div class="text-subtitle-1 font-weight-medium mb-2">Description</div>
                <div class="text-body-1">{{ task.description || 'No description provided' }}</div>
              </div>

              <!-- Additional Details -->
              <div class="mt-6">
                <v-row>
                  <v-col cols="12" sm="6">
                    <div class="d-flex align-center mb-3">
                      <v-icon icon="mdi-calendar" size="small" class="me-2 text-medium-emphasis" />
                      <span class="text-body-2 text-medium-emphasis me-2">Created:</span>
                      <span class="text-body-2">
                        {{ formatDate(task.created_at) }}
                      </span>
                    </div>
                    <div class="d-flex align-center mb-3">
                      <v-icon icon="mdi-account" size="small" class="me-2 text-medium-emphasis" />
                      <span class="text-body-2 text-medium-emphasis me-2">Created by:</span>
                      <span class="text-body-2">{{ task.assigned_by.username }}</span>
                    </div>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <div v-if="task.completed_at" class="d-flex align-center mb-3">
                      <v-icon icon="mdi-check-circle" size="small" class="me-2 text-success" />
                      <span class="text-body-2 text-medium-emphasis me-2">Completed:</span>
                      <span class="text-body-2">
                        {{ formatDate(task.completed_at) }}
                      </span>
                    </div>
                    <div v-if="task.completed_by" class="d-flex align-center mb-3">
                      <v-icon icon="mdi-account-check" size="small" class="me-2 text-success" />
                      <span class="text-body-2 text-medium-emphasis me-2">Completed by:</span>
                      <span class="text-body-2">{{ task.completed_by.username }}</span>
                    </div>
                  </v-col>
                </v-row>
              </div>

              <!-- Custom Fields -->
              <div v-if="customFields.length > 0" class="mt-6">
                <v-divider class="mb-4" />
                <div class="text-subtitle-1 font-weight-medium mb-3">Additional Information</div>
                <v-row>
                  <v-col v-for="field in customFields" :key="field.name" cols="12" sm="6" md="4">
                    <div class="mb-3">
                      <div class="d-flex align-center mb-1">
                        <span class="text-body-2 text-medium-emphasis">{{ field.label }}</span>
                        <v-btn
                          v-if="canEditTask && editingCustomField !== field.name"
                          icon="mdi-pencil"
                          size="x-small"
                          variant="text"
                          class="ml-1"
                          @click="startEditingField(field)"
                        >
                          <v-tooltip activator="parent" location="top"
                            >Edit {{ field.label }}</v-tooltip
                          >
                        </v-btn>
                      </div>
                      <div v-if="editingCustomField === field.name" class="mb-2">
                        <CustomFieldInput v-model="customFieldValues[field.name]" :field="field" />
                        <div class="d-flex mt-2">
                          <v-btn size="small" variant="tonal" @click="cancelFieldEdit"
                            >Cancel</v-btn
                          >
                          <v-btn
                            size="small"
                            color="primary"
                            variant="flat"
                            class="ml-2"
                            @click="saveFieldEdit(field)"
                          >
                            Save
                          </v-btn>
                        </div>
                      </div>
                      <div v-else class="text-body-2">
                        <span v-if="field.type === 'boolean'">
                          <v-icon
                            :icon="
                              task.custom_fields[field.name]
                                ? 'mdi-check-circle'
                                : 'mdi-close-circle'
                            "
                            :color="task.custom_fields[field.name] ? 'success' : 'error'"
                            size="small"
                            class="me-1"
                          />
                          {{ task.custom_fields[field.name] ? 'Yes' : 'No' }}
                        </span>
                        <span v-else-if="field.type === 'date' && task.custom_fields[field.name]">
                          {{ formatDateOnly(task.custom_fields[field.name]) }}
                        </span>
                        <span v-else>
                          {{ task.custom_fields[field.name] || 'Not provided' }}
                        </span>
                      </div>
                      <div v-if="field.description" class="text-caption text-medium-emphasis mt-1">
                        {{ field.description }}
                      </div>
                    </div>
                  </v-col>
                </v-row>
              </div>
            </v-col>

            <v-col cols="12" lg="4">
              <v-card variant="outlined">
                <v-card-text class="pa-4">
                  <!-- Status -->
                  <div class="mb-4">
                    <div class="text-body-2 text-medium-emphasis mb-1">Status</div>
                    <v-chip
                      :color="TASK_STATUS_COLORS[task.status]"
                      size="small"
                      :class="{ 'cursor-pointer': canEditTask }"
                      @click="canEditTask && openStatusDialog()"
                    >
                      {{ TASK_STATUS_LABELS[task.status] }}
                    </v-chip>
                  </div>

                  <!-- Priority -->
                  <div class="mb-4">
                    <div class="text-body-2 text-medium-emphasis mb-1">Priority</div>
                    <v-chip :color="TASK_PRIORITY_COLORS[task.priority]" size="small">
                      <v-icon size="small" start>{{ TASK_PRIORITY_ICONS[task.priority] }}</v-icon>
                      {{ TASK_PRIORITY_LABELS[task.priority] }}
                    </v-chip>
                  </div>

                  <!-- Assignee -->
                  <div class="mb-4">
                    <div class="text-body-2 text-medium-emphasis mb-1">Assigned To</div>
                    <div class="d-flex align-center">
                      <span v-if="task.assigned_to" class="text-body-2">
                        {{ task.assigned_to.username }}
                      </span>
                      <span v-else class="text-body-2 text-medium-emphasis">Unassigned</span>
                      <v-btn
                        v-if="canAssignTask"
                        class="ml-2"
                        icon="mdi-pencil"
                        size="x-small"
                        variant="text"
                        @click="openAssignDialog"
                      >
                        <v-tooltip activator="parent" location="top">Change assignee</v-tooltip>
                      </v-btn>
                    </div>
                  </div>

                  <!-- Case -->
                  <div class="mb-4">
                    <div class="text-body-2 text-medium-emphasis mb-1">Case</div>
                    <v-btn
                      variant="text"
                      size="small"
                      color="primary"
                      :to="`/case/${task.case_id}`"
                    >
                      Case #{{ task.case_id }}
                    </v-btn>
                  </div>

                  <!-- Due Date -->
                  <div v-if="task.due_date" class="mb-4">
                    <div class="text-body-2 text-medium-emphasis mb-1">Due Date</div>
                    <div :class="{ 'text-error': isOverdue }" class="text-body-2">
                      <v-icon
                        v-if="isOverdue"
                        icon="mdi-alert"
                        size="small"
                        color="error"
                        class="me-1"
                      />
                      {{ formatDateOnly(task.due_date) }}
                    </div>
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </div>
  </BaseDashboard>

  <!-- Edit Dialog -->
  <v-dialog v-model="editMode" max-width="600" persistent>
    <TaskForm :task="task" @cancel="editMode = false" @save="handleUpdate" />
  </v-dialog>

  <!-- Assign Dialog -->
  <v-dialog v-model="showAssignDialog" max-width="400">
    <TaskAssignDialog :task="task" @assign="handleAssign" @cancel="showAssignDialog = false" />
  </v-dialog>

  <!-- Status Dialog -->
  <v-dialog v-model="showStatusDialog" max-width="400">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start icon="mdi-progress-check" />
        Update Status
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <v-select
          v-model="newStatus"
          :items="statusOptions"
          label="New Status"
          variant="outlined"
          density="comfortable"
        />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="text" @click="showStatusDialog = false">Cancel</v-btn>
        <v-btn color="primary" variant="flat" @click="handleStatusUpdate">Update</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Quick Edit Dialog -->
  <v-dialog v-model="showQuickEditDialog" max-width="600" persistent>
    <TaskQuickEditDialog
      :task="task"
      :custom-fields="customFields"
      :is-user-case-lead="isUserCaseLead"
      @cancel="showQuickEditDialog = false"
      @save="handleQuickUpdate"
    />
  </v-dialog>
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
import TaskQuickEditDialog from '@/components/tasks/TaskQuickEditDialog.vue'
import CustomFieldInput from '@/components/tasks/CustomFieldInput.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'
import { formatDate, formatDateOnly } from '@/composables/dateUtils'
import { caseService } from '@/services/case'

const route = useRoute()
const taskStore = useTaskStore()
const authStore = useAuthStore()

// Data
const editMode = ref(false)
const showAssignDialog = ref(false)
const showStatusDialog = ref(false)
const showQuickEditDialog = ref(false)
const editingCustomField = ref(null)
const newStatus = ref('')
const isEditing = ref(false)
const customFields = ref([])
const customFieldValues = ref({})
const isUserCaseLead = ref(false)

// Computed
const taskId = computed(() => parseInt(route.params.id))
const task = computed(() => taskStore.currentTask)
const loading = computed(() => taskStore.loading)
const error = computed(() => taskStore.error)

const canEditTask = computed(() => {
  if (!task.value) return false
  // Admin, case lead, or assigned user can edit
  return (
    authStore.user?.role === 'Admin' ||
    isUserCaseLead.value ||
    task.value.assigned_to_id === authStore.user?.id
  )
})

const canEditFull = computed(() => {
  if (!task.value) return false
  // Only admin or case lead can do full edits
  return authStore.user?.role === 'Admin' || isUserCaseLead.value
})

const canEditLimited = computed(() => {
  if (!task.value) return false
  // Assigned users have limited edit capabilities
  return (
    task.value.assigned_to_id === authStore.user?.id &&
    authStore.user?.role !== 'Admin' &&
    !isUserCaseLead.value
  )
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
// Remove local formatDate and formatDateTime - using imported ones from dateUtils

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

async function handleQuickUpdate(updates) {
  await taskStore.updateTask(taskId.value, updates)
  showQuickEditDialog.value = false
}

function startEditingField(field) {
  editingCustomField.value = field.name
  customFieldValues.value[field.name] =
    task.value.custom_fields[field.name] || (field.type === 'boolean' ? false : '')
}

function cancelFieldEdit() {
  editingCustomField.value = null
  customFieldValues.value = {}
}

async function saveFieldEdit(field) {
  const updates = {
    custom_fields: {
      ...task.value.custom_fields,
      [field.name]: customFieldValues.value[field.name],
    },
  }
  await taskStore.updateTask(taskId.value, updates)
  editingCustomField.value = null
  customFieldValues.value = {}
}

// Lifecycle
onMounted(async () => {
  await taskStore.loadTask(taskId.value)
  await taskStore.loadTemplates()

  // Check if user is a case lead
  if (task.value?.case_id && authStore.user) {
    try {
      const caseData = await caseService.getCase(task.value.case_id)
      const currentUserInCase = caseData.users?.find((u) => u.id === authStore.user.id)
      isUserCaseLead.value = currentUserInCase?.is_lead || false
    } catch (error) {
      console.error('Failed to fetch case data:', error)
      isUserCaseLead.value = false
    }
  }

  // Load custom fields from template if task has one
  if (task.value?.template_id) {
    const templates = taskStore.templates
    const template = templates.find((t) => t.id === task.value.template_id)
    if (template?.definition_json?.fields) {
      customFields.value = template.definition_json.fields
    }
  }
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
