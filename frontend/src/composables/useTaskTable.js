import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import { formatDateOnly } from '@/composables/dateUtils'

export function useTaskTable() {
  const router = useRouter()
  const taskStore = useTaskStore()
  const authStore = useAuthStore()

  // Dialog states
  const showAssignDialog = ref(false)
  const showStatusDialog = ref(false)
  const selectedTask = ref(null)
  const newStatus = ref('')

  // Permissions
  const canCreateTasks = computed(() => {
    return authStore.user?.role !== 'Analyst'
  })

  const canAssignTasks = computed(() => {
    return authStore.user?.role !== 'Analyst'
  })

  // Check if user can delete a specific task
  const canDeleteTask = () => {
    // Admin can always delete
    if (authStore.user?.role === 'Admin') {
      return true
    }

    // For now, we can't check is_lead status from frontend
    // This will need to be added to the task or case data from backend
    // TODO: Add is_lead information to task/case response
    return false
  }

  // Status options for the status update dialog
  const statusOptions = computed(() =>
    Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({ title, value })),
  )

  // Common table headers
  const headers = [
    { title: 'Title', key: 'title', sortable: true },
    { title: 'Priority', key: 'priority', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Assignee', key: 'assignee', sortable: true },
    { title: 'Due Date', key: 'due_date', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false },
  ]

  // Headers with case column for main dashboard
  const headersWithCase = [
    { title: 'Title', key: 'title', sortable: true },
    { title: 'Case', key: 'case', sortable: true },
    { title: 'Priority', key: 'priority', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Assigned To', key: 'assignee', sortable: true },
    { title: 'Due Date', key: 'due_date', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false },
  ]

  // Methods
  function formatDate(date) {
    return formatDateOnly(date)
  }

  function isOverdue(task) {
    if (!task.due_date || task.status === TASK_STATUS.COMPLETED) return false
    return new Date(task.due_date) < new Date()
  }

  function handleRowClick(event, { item }) {
    router.push(`/tasks/${item.id}`)
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

  // Note: Delete confirmation is handled by the component using ConfirmationDialog
  // This returns the task to be deleted
  function prepareDeleteTask(task) {
    return task
  }

  async function deleteTask(taskId) {
    try {
      await taskStore.deleteTask(taskId)
      return true
    } catch (error) {
      console.error('Failed to delete task:', error)
      throw error
    }
  }

  return {
    // State
    showAssignDialog,
    showStatusDialog,
    selectedTask,
    newStatus,

    // Computed
    canCreateTasks,
    canAssignTasks,
    canDeleteTask,
    statusOptions,
    headers,
    headersWithCase,

    // Methods
    formatDate,
    isOverdue,
    handleRowClick,
    openAssignDialog,
    openStatusDialog,
    prepareDeleteTask,
    deleteTask,
    handleAssign,
    handleStatusUpdate,

    // Constants (for template access)
    TASK_STATUS_COLORS,
    TASK_STATUS_LABELS,
    TASK_PRIORITY_COLORS,
    TASK_PRIORITY_LABELS,
    TASK_PRIORITY_ICONS,
  }
}
