import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import taskService from '@/services/task'
import { TASK_STATUS } from '@/constants/tasks'
import { useActiveCaseStore } from './activeCase'
import { useAuthStore } from './auth'

export const useTaskStore = defineStore('task', () => {
  const activeCase = useActiveCaseStore()
  const authStore = useAuthStore()
  let listRequest = 0
  let detailRequest = 0
  let contextGeneration = 0
  const templates = ref([])
  const tasks = ref([])
  const currentTask = ref(null)
  const loading = ref(false)
  const error = ref(null)

  watch(
    [() => activeCase.activeCaseId, () => authStore.user?.id],
    () => {
      contextGeneration++
      listRequest++
      detailRequest++
      tasks.value = []
      currentTask.value = null
      loading.value = false
      error.value = null
    },
    { flush: 'sync' },
  )

  const currentUserId = computed(() => authStore.user?.id)

  const myTasks = computed(() =>
    tasks.value.filter((t) => t.assigned_to_id === currentUserId.value),
  )

  const overdueTasks = computed(() =>
    tasks.value.filter((t) => {
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

  async function loadTasks(isCurrent = () => true) {
    const caseId = activeCase.activeCaseId
    if (!caseId) return
    const request = ++listRequest
    try {
      loading.value = true
      error.value = null
      const result = await taskService.getTasks({ case_id: caseId })
      if (request === listRequest && isCurrent()) tasks.value = result
    } catch (err) {
      if (request !== listRequest || !isCurrent()) return
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

  async function mutate(call, errorMessage) {
    try {
      loading.value = true
      error.value = null
      const updated = await call()
      const index = tasks.value.findIndex((t) => t.id === updated.id)
      if (index !== -1) tasks.value[index] = updated
      if (currentTask.value?.id === updated.id) currentTask.value = updated
      return updated
    } catch (err) {
      error.value = err.response?.data?.detail || errorMessage
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateTask = (taskId, updates) =>
    mutate(() => taskService.updateTask(taskId, updates), 'Failed to update task')

  async function deleteTask(taskId) {
    try {
      loading.value = true
      error.value = null
      await taskService.deleteTask(taskId)

      tasks.value = tasks.value.filter((t) => t.id !== taskId)

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

  const assignTask = (taskId, userId) =>
    mutate(() => taskService.assignTask(taskId, userId), 'Failed to assign task')

  const updateTaskStatus = (taskId, status) =>
    mutate(() => taskService.updateStatus(taskId, status), 'Failed to update task status')

  async function applyBulk(operation, taskIds, value, isCurrent = () => true) {
    const generation = contextGeneration
    const caseId = activeCase.activeCaseId
    const ids = [...new Set(taskIds)]
    if (!caseId || !ids.length) throw new Error('Select Tasks in an active case first')
    const sameContext = () => generation === contextGeneration
    try {
      loading.value = true
      error.value = null
      const updated = await operation(ids, value)
      if (sameContext() && isCurrent()) {
        updated.forEach((task) => {
          if (task.case_id !== caseId || !ids.includes(task.id)) return
          const index = tasks.value.findIndex((item) => item.id === task.id)
          if (index !== -1) tasks.value[index] = task
          if (currentTask.value?.id === task.id) currentTask.value = task
        })
      }
      return updated
    } catch (err) {
      if (sameContext() && isCurrent()) {
        error.value = err.response?.data?.detail || 'Unable to confirm bulk Task updates'
      }
      throw err
    } finally {
      if (sameContext()) loading.value = false
    }
  }

  function bulkAssign(taskIds, userId, isCurrent) {
    return applyBulk(taskService.bulkAssign, taskIds, userId, isCurrent)
  }

  function bulkUpdateStatus(taskIds, status, isCurrent) {
    return applyBulk(taskService.bulkUpdateStatus, taskIds, status, isCurrent)
  }

  return {
    templates,
    tasks,
    currentTask,
    loading,
    error,

    myTasks,
    overdueTasks,
    stats,

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
  }
})
