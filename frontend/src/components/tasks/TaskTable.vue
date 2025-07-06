<template>
  <div>
    <!-- Tasks Table -->
    <v-data-table
      v-model="selectedItems"
      :headers="computedHeaders"
      :items="tasks"
      :loading="loading"
      :show-select="showSelect"
      class="tasks-table"
      hover
      item-value="id"
      @click:row="handleRowClick"
    >
      <!-- Title Column -->
      <template #[`item.title`]="{ item }">
        {{ item.title }}
      </template>

      <!-- Case Column (only if showCase is true) -->
      <template v-if="showCase" #[`item.case`]="{ item }"> Case #{{ item.case_id }} </template>

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
            @click.stop="openAssignDialog(item)"
          >
            <v-icon>mdi-account-plus</v-icon>
            <v-tooltip activator="parent" location="top">Assign Task</v-tooltip>
          </v-btn>
          <v-btn icon size="small" variant="text" @click.stop="openStatusDialog(item)">
            <v-icon>mdi-progress-check</v-icon>
            <v-tooltip activator="parent" location="top">Update Status</v-tooltip>
          </v-btn>
          <v-btn
            v-if="canDeleteTask(item)"
            color="error"
            icon
            size="small"
            variant="text"
            @click.stop="handleDeleteClick(item)"
          >
            <v-icon>mdi-delete</v-icon>
            <v-tooltip activator="parent" location="top">Delete Task</v-tooltip>
          </v-btn>
        </div>
      </template>

      <!-- Empty state -->
      <template #no-data>
        <div class="text-center pa-12">
          <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-format-list-checks" size="64" />
          <h3 class="text-h6 font-weight-medium mb-2">
            <slot name="empty-title">No tasks yet</slot>
          </h3>
          <p class="text-body-2 text-medium-emphasis mb-4">
            <slot name="empty-message">Get started by creating your first task.</slot>
          </p>
          <slot name="empty-action" />
        </div>
      </template>
    </v-data-table>

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

    <!-- Confirmation Dialog -->
    <ConfirmationDialog ref="confirmDialog" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useTaskTable } from '@/composables/useTaskTable'
import TaskAssignDialog from './TaskAssignDialog.vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'

const props = defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  showCase: {
    type: Boolean,
    default: false,
  },
  showSelect: {
    type: Boolean,
    default: false,
  },
  modelValue: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue'])

// Refs
const confirmDialog = ref(null)

const selectedItems = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const {
  showAssignDialog,
  showStatusDialog,
  selectedTask,
  newStatus,
  canAssignTasks,
  canDeleteTask,
  statusOptions,
  headers,
  headersWithCase,
  formatDate,
  isOverdue,
  handleRowClick,
  openAssignDialog,
  openStatusDialog,
  deleteTask,
  handleAssign,
  handleStatusUpdate,
  TASK_STATUS_COLORS,
  TASK_STATUS_LABELS,
  TASK_PRIORITY_COLORS,
  TASK_PRIORITY_LABELS,
  TASK_PRIORITY_ICONS,
} = useTaskTable()

// Use appropriate headers based on showCase prop
const computedHeaders = computed(() => (props.showCase ? headersWithCase : headers))

// Handle delete with confirmation
async function handleDeleteClick(task) {
  try {
    await confirmDialog.value.confirmDelete(`task "${task.title}"`)
    await deleteTask(task.id)
  } catch (error) {
    // User cancelled or delete failed
    if (error !== false) {
      // Only log if it's not a user cancellation
      console.error('Delete operation failed:', error)
    }
  }
}
</script>

<style scoped>
.tasks-table :deep(.v-data-table__tr:hover) {
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.tasks-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.tasks-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}

.tasks-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>
