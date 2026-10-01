import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables/useNotifications'
import { TASK_STATUS } from '@/constants/tasks'

export function useTaskTable() {
  const router = useRouter()
  const taskStore = useTaskStore()
  const authStore = useAuthStore()
  const { snackbar, showError, showSuccess } = useNotifications()

  // Dialog states
  const showAssignDialog = ref(false)
  const showStatusDialog = ref(false)
  const selectedTask = ref(null)
  const newStatus = ref('')

  // Permissions
  const canCreateTasks = computed(() => {
    return authStore.user?.role !== 'Analyst'
  })

  // Check if user can delete a specific task
  const canDeleteTask = () => {
    // Only admins can delete tasks
    return authStore.user?.role === 'Admin'
  }

  // Common table headers
  const headers = [
    { title: 'Title', key: 'title', sortable: true },
    { title: 'Priority', key: 'priority', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Assignee', key: 'assignee', sortable: true },
    { title: 'Due Date', key: 'due_date', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false },
  ]

  // Methods
  function isOverdue(task) {
    if (!task.due_date || task.status === TASK_STATUS.COMPLETED) return false
    return new Date(task.due_date) < new Date()
  }

  function handleRowClick(event, { item }) {
    router.push(`/case/${item.case_id}/tasks/${item.id}`)
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
    try {
      await taskStore.assignTask(selectedTask.value.id, userId)
      showAssignDialog.value = false
      selectedTask.value = null
      showSuccess('Task assigned successfully')
    } catch (error) {
      console.error('Failed to assign task:', error)
      if (error.response?.status === 403) {
        showError(
          'You do not have permission to assign this task. Only admins and case leads can assign tasks.',
        )
      } else {
        showError(error.response?.data?.detail || 'Failed to assign task')
      }
    }
  }

  async function handleStatusUpdate() {
    try {
      await taskStore.updateTaskStatus(selectedTask.value.id, newStatus.value)
      showStatusDialog.value = false
      selectedTask.value = null
      showSuccess('Task status updated successfully')
    } catch (error) {
      console.error('Failed to update task status:', error)
      if (error.response?.status === 403) {
        showError('You do not have permission to update this task')
      } else {
        showError(error.response?.data?.detail || 'Failed to update task status')
      }
    }
  }

  return {
    snackbar,
    // State
    showAssignDialog,
    showStatusDialog,
    selectedTask,
    newStatus,

    // Computed
    canCreateTasks,
    canDeleteTask,
    headers,

    // Methods
    isOverdue,
    handleRowClick,
    openAssignDialog,
    openStatusDialog,
    handleAssign,
    handleStatusUpdate,
  }
}
