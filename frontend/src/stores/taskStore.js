import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import taskService from '@/services/task'
import { TASK_STATUS } from '@/constants/tasks'
import { useActiveCaseStore } from './activeCase'
import { useAuthStore } from './auth'

export const useTaskStore = defineStore('task', () => {
  const activeCase = useActiveCaseStore()
  let listRequest = 0
  let detailRequest = 0
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
  })

  watch(
    () => activeCase.activeCaseId,
    () => {
      listRequest++
      detailRequest++
      tasks.value = []
      currentTask.value = null
      loading.value = false
      error.value = null
      resetFilters()
    },
    { flush: 'sync' },
  )

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
      // Don't set the global loading state for template loading
      // This was causing infinite re-renders in TaskDashboard
      templates.value = await taskService.getTemplates()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load templates'
      throw err
    }
  }

  async function loadTasks(customFilters = null) {
    const caseId = activeCase.activeCaseId
    if (!caseId) return
    const request = ++listRequest
    try {
      loading.value = true
      error.value = null

      const filterParams = customFilters || {
        status: filters.value.status !== 'all' ? filters.value.status : undefined,
        priority: filters.value.priority !== 'all' ? filters.value.priority : undefined,
        assigned_to_id:
          filters.value.assignee !== 'all' &&
          filters.value.assignee !== 'unassigned' &&
          filters.value.assignee !== 'me'
            ? filters.value.assignee
            : undefined,
      }

      filterParams.case_id = caseId

      // Remove undefined values
      Object.keys(filterParams).forEach((key) => {
        if (filterParams[key] === undefined) {
          delete filterParams[key]
        }
      })

      const result = await taskService.getTasks(filterParams)
      if (request === listRequest) tasks.value = result
    } catch (err) {
      if (request !== listRequest) return
      error.value = err.response?.data?.detail || 'Failed to load tasks'
      throw err
    } finally {
      if (request === listRequest) loading.value = false
    }
  }

  async function loadTask(taskId) {
    const caseId = activeCase.activeCaseId
    if (!caseId) return
    const request = ++detailRequest
    currentTask.value = null
    try {
      loading.value = true
      error.value = null
      const task = await taskService.getTask(taskId)
      if (request !== detailRequest) return
      if (task.case_id !== caseId) throw new Error('Task does not belong to the active case')
      currentTask.value = task
      return currentTask.value
    } catch (err) {
      if (request !== detailRequest) return
      error.value = err.response?.data?.detail || 'Failed to load task'
      throw err
    } finally {
      if (request === detailRequest) loading.value = false
    }
  }

  async function createTask(taskData) {
    const caseId = activeCase.activeCaseId
    if (!caseId || (taskData.case_id != null && taskData.case_id !== caseId)) {
      throw new Error('An active case matching the task is required')
    }
    try {
      loading.value = true
      error.value = null
      const newTask = await taskService.createTask({ ...taskData, case_id: caseId })
      if (activeCase.activeCaseId === caseId) tasks.value.push(newTask)
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
