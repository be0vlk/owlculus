import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import taskService from '@/services/task'
import { TASK_STATUS } from '@/constants/tasks'
import { useAuthStore } from './auth'

export const useTaskStore = defineStore('task', () => {
  // State
  const templates = ref([])
  const tasks = ref([])
  const currentTask = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({
    status: 'all',
    priority: 'all',
    assignee: 'all',
    case_id: null,
  })

  // Getters
  const authStore = useAuthStore()
  const currentUserId = computed(() => authStore.user?.id)

  const filteredTasks = computed(() => {
    let result = tasks.value

    if (filters.value.status !== 'all') {
      result = result.filter((t) => t.status === filters.value.status)
    }

    if (filters.value.priority !== 'all') {
      result = result.filter((t) => t.priority === filters.value.priority)
    }

    if (filters.value.assignee !== 'all') {
      if (filters.value.assignee === 'unassigned') {
        result = result.filter((t) => !t.assigned_to_id)
      } else if (filters.value.assignee === 'me') {
        result = result.filter((t) => t.assigned_to_id === currentUserId.value)
      } else {
        result = result.filter((t) => t.assigned_to_id === parseInt(filters.value.assignee))
      }
    }

    if (filters.value.case_id) {
      result = result.filter((t) => t.case_id === filters.value.case_id)
    }

    return result
  })

  const tasksByStatus = computed(() => {
    const grouped = {}
    Object.values(TASK_STATUS).forEach((status) => {
      grouped[status] = filteredTasks.value.filter((t) => t.status === status)
    })
    return grouped
  })

  const myTasks = computed(() =>
    tasks.value.filter((t) => t.assigned_to_id === currentUserId.value),
  )

  const myOpenTasks = computed(() =>
    myTasks.value.filter((t) => t.status !== TASK_STATUS.COMPLETED),
  )

  const overdueTasks = computed(() =>
    filteredTasks.value.filter((t) => {
      if (!t.due_date || t.status === TASK_STATUS.COMPLETED) return false
      return new Date(t.due_date) < new Date()
    }),
  )

  const stats = computed(() => ({
    total: tasks.value.length,
    myTasks: myTasks.value.length,
    overdue: overdueTasks.value.length,
    completed: tasks.value.filter((t) => t.status === TASK_STATUS.COMPLETED).length,
  }))

  // Actions
  async function loadTemplates() {
    try {
      loading.value = true
      error.value = null
      templates.value = await taskService.getTemplates()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load templates'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadTasks(customFilters = null) {
    try {
      loading.value = true
      error.value = null

      const filterParams = customFilters || {
        case_id: filters.value.case_id,
        status: filters.value.status !== 'all' ? filters.value.status : undefined,
        priority: filters.value.priority !== 'all' ? filters.value.priority : undefined,
        assigned_to_id:
          filters.value.assignee !== 'all' &&
          filters.value.assignee !== 'unassigned' &&
          filters.value.assignee !== 'me'
            ? filters.value.assignee
            : undefined,
      }

      // Remove undefined values
      Object.keys(filterParams).forEach((key) => {
        if (filterParams[key] === undefined) {
          delete filterParams[key]
        }
      })

      tasks.value = await taskService.getTasks(filterParams)
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load tasks'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadTask(taskId) {
    try {
      loading.value = true
      error.value = null
      currentTask.value = await taskService.getTask(taskId)
      return currentTask.value
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load task'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createTask(taskData) {
    try {
      loading.value = true
      error.value = null
      const newTask = await taskService.createTask(taskData)
      tasks.value.push(newTask)
      return newTask
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to create task'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateTask(taskId, updates) {
    try {
      loading.value = true
      error.value = null
      const updated = await taskService.updateTask(taskId, updates)

      // Update in tasks array
      const index = tasks.value.findIndex((t) => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = updated
      }

      // Update current task if it's the same
      if (currentTask.value?.id === taskId) {
        currentTask.value = updated
      }

      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to update task'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteTask(taskId) {
    try {
      loading.value = true
      error.value = null
      await taskService.deleteTask(taskId)

      // Remove from tasks array
      tasks.value = tasks.value.filter((t) => t.id !== taskId)

      // Clear current task if it was deleted
      if (currentTask.value?.id === taskId) {
        currentTask.value = null
      }
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete task'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function assignTask(taskId, userId) {
    try {
      loading.value = true
      error.value = null
      const updated = await taskService.assignTask(taskId, userId)

      // Update in tasks array
      const index = tasks.value.findIndex((t) => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = updated
      }

      // Update current task if it's the same
      if (currentTask.value?.id === taskId) {
        currentTask.value = updated
      }

      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to assign task'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateTaskStatus(taskId, status) {
    try {
      loading.value = true
      error.value = null
      const updated = await taskService.updateStatus(taskId, status)

      // Update in tasks array
      const index = tasks.value.findIndex((t) => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = updated
      }

      // Update current task if it's the same
      if (currentTask.value?.id === taskId) {
        currentTask.value = updated
      }

      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to update task status'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function bulkAssign(taskIds, userId) {
    try {
      loading.value = true
      error.value = null
      const updated = await taskService.bulkAssign(taskIds, userId)

      // Update tasks in array
      updated.forEach((updatedTask) => {
        const index = tasks.value.findIndex((t) => t.id === updatedTask.id)
        if (index !== -1) {
          tasks.value[index] = updatedTask
        }
      })

      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to bulk assign tasks'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function bulkUpdateStatus(taskIds, status) {
    try {
      loading.value = true
      error.value = null
      const updated = await taskService.bulkUpdateStatus(taskIds, status)

      // Update tasks in array
      updated.forEach((updatedTask) => {
        const index = tasks.value.findIndex((t) => t.id === updatedTask.id)
        if (index !== -1) {
          tasks.value[index] = updatedTask
        }
      })

      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to bulk update status'
      throw err
    } finally {
      loading.value = false
    }
  }

  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
  }

  function resetFilters() {
    filters.value = {
      status: 'all',
      priority: 'all',
      assignee: 'all',
      case_id: null,
    }
  }

  return {
    // State
    templates,
    tasks,
    currentTask,
    loading,
    error,
    filters,

    // Getters
    filteredTasks,
    tasksByStatus,
    myTasks,
    myOpenTasks,
    overdueTasks,
    stats,

    // Actions
    loadTemplates,
    loadTasks,
    loadTask,
    createTask,
    updateTask,
    deleteTask,
    assignTask,
    updateTaskStatus,
    bulkAssign,
    bulkUpdateStatus,
    setFilters,
    resetFilters,
  }
})
