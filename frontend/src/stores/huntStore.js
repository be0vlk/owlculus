import { observeExecution } from '@/services/observeExecution'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { huntService } from '../services/hunt'

export const useHuntStore = defineStore('hunt', () => {
  let generation = 0
  // State
  const availableHunts = ref([])
  const activeExecutions = ref({})
  const executionHistory = ref([])
  const loading = ref(false)
  const error = ref(null)
  const observations = new Map()

  // Getters
  const huntsByCategory = computed(() => {
    const categorized = {}
    availableHunts.value.forEach((hunt) => {
      if (!categorized[hunt.category]) {
        categorized[hunt.category] = []
      }
      categorized[hunt.category].push(hunt)
    })
    return categorized
  })

  const runningExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter((execution) =>
      ['pending', 'running', 'cancelling'].includes(execution.status),
    )
  })

  const completedExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter(
      (execution) => execution.status === 'completed' || execution.status === 'partial',
    )
  })

  const failedExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter(
      (execution) => execution.status === 'failed',
    )
  })

  // Actions
  async function fetchHunts() {
    try {
      loading.value = true
      error.value = null
      const hunts = await huntService.getHunts()
      availableHunts.value = hunts
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch hunts'
      console.error('Failed to fetch hunts:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function getHunt(huntId) {
    try {
      const hunt = await huntService.getHunt(huntId)
      return hunt
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch hunt'
      console.error('Failed to fetch hunt:', err)
      throw err
    }
  }

  async function executeHunt(huntId, caseId, parameters) {
    const request = generation
    try {
      error.value = null
      const execution = await huntService.executeHunt(huntId, caseId, parameters)

      // Fetch full execution details including steps
      let fullExecution = execution
      try {
        fullExecution = await huntService.getExecution(execution.id, true)
      } catch (err) {
        console.error('Failed to fetch full execution details:', err)
      }

      if (request !== generation) return fullExecution

      // Add to active executions with full data - ensure reactivity
      activeExecutions.value = {
        ...activeExecutions.value,
        [fullExecution.id]: fullExecution,
      }

      // Also add to execution history
      executionHistory.value.unshift(fullExecution)
      executionHistory.value.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

      // Start durable observation
      if (['pending', 'running', 'cancelling'].includes(fullExecution.status)) {
        subscribeToExecution(fullExecution.id)
      }

      return fullExecution
    } catch (err) {
      if (request === generation)
        error.value = err.response?.data?.detail || 'Failed to execute hunt'
      console.error('Failed to execute hunt:', err)
      throw err
    }
  }

  async function getExecution(executionId, includeSteps = false) {
    const request = generation
    try {
      const execution = await huntService.getExecution(executionId, includeSteps)

      // Update active executions
      if (request === generation) activeExecutions.value[execution.id] = execution

      return execution
    } catch (err) {
      if (request === generation)
        error.value = err.response?.data?.detail || 'Failed to fetch execution'
      console.error('Failed to fetch execution:', err)
      throw err
    }
  }

  async function getCaseExecutions(caseId) {
    resetCaseExecutions()
    const request = generation
    if (!caseId) return []
    try {
      const executions = await huntService.getCaseExecutions(caseId)
      if (request !== generation) return []
      executionHistory.value = executions
      activeExecutions.value = Object.fromEntries(
        executions.map((execution) => [execution.id, execution]),
      )
      await Promise.all(
        executions
          .filter((execution) => ['running', 'pending', 'cancelling'].includes(execution.status))
          .map(async (execution) => {
            try {
              await getExecution(execution.id, true)
            } catch {
              // The list response still provides usable progress if details fail.
            }
            if (request === generation) subscribeToExecution(execution.id)
          }),
      )
      return request === generation ? executions : []
    } catch (err) {
      if (request !== generation) return []
      error.value = err.response?.data?.detail || 'Failed to fetch case executions'
      throw err
    }
  }

  async function cancelExecution(executionId) {
    const request = generation
    try {
      error.value = null
      const result = await huntService.cancelExecution(executionId)
      if (request !== generation) return result

      // Update execution status
      const execution = activeExecutions.value[executionId]
      if (execution?.revision && result.revision < execution.revision) return result
      if (execution) {
        execution.status = result.status
        execution.revision = result.revision
        activeExecutions.value[executionId] = execution
      }

      if (['pending', 'running', 'cancelling'].includes(result.status))
        subscribeToExecution(executionId)
      else unsubscribeFromExecution(executionId)

      return result
    } catch (err) {
      if (request === generation)
        error.value = err.response?.data?.detail || 'Failed to cancel execution'
      console.error('Failed to cancel execution:', err)
      throw err
    }
  }

  function subscribeToExecution(executionId) {
    if (observations.has(executionId)) return
    const request = generation
    const observation = { stop: null }
    observations.set(executionId, observation)
    const current = () => request === generation && observations.get(executionId) === observation
    observation.stop = observeExecution({
      async refresh(signal) {
        const execution = await huntService.getExecution(executionId, true, signal)
        if (!current()) return { terminal: true }
        const previous = activeExecutions.value[executionId]
        if ((execution.revision ?? 0) < (previous?.revision ?? 0)) return {}
        activeExecutions.value[executionId] = execution
        const index = executionHistory.value.findIndex((item) => item.id === executionId)
        if (index >= 0) executionHistory.value[index] = execution
        error.value = null
        const terminal = !['pending', 'running', 'cancelling'].includes(execution.status)
        if (terminal) observations.delete(executionId)
        return { terminal }
      },
      openStream: (...args) => huntService.createExecutionStream(executionId, ...args),
      closeStream: huntService.closeExecutionStream,
      onError(message) {
        if (current()) error.value = message
      },
    })
  }

  function unsubscribeFromExecution(executionId) {
    const observation = observations.get(executionId)
    if (!observation) return
    observations.delete(executionId)
    observation.stop?.()
  }

  function clearError() {
    error.value = null
  }

  function removeExecution(executionId) {
    delete activeExecutions.value[executionId]
    unsubscribeFromExecution(executionId)
  }

  // Refresh all running executions with latest data
  async function refreshRunningExecutions() {
    const request = generation
    const runningExecs = runningExecutions.value
    if (runningExecs.length === 0) return

    try {
      const refreshPromises = runningExecs.map(async (execution) => {
        try {
          const updated = await huntService.getExecution(execution.id, true)

          if (request !== generation) return

          // Update in activeExecutions
          activeExecutions.value = {
            ...activeExecutions.value,
            [updated.id]: updated,
          }

          // If execution is no longer running, update history
          if (updated.status !== 'running' && updated.status !== 'pending') {
            const historyIndex = executionHistory.value.findIndex((e) => e.id === updated.id)
            if (historyIndex !== -1) {
              executionHistory.value[historyIndex] = { ...updated }
            } else {
              executionHistory.value.unshift({ ...updated })
            }

            // Sort history by creation date
            executionHistory.value.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
          }

          return updated
        } catch (err) {
          console.error(`Failed to refresh execution ${execution.id}:`, err)
          return execution
        }
      })

      await Promise.all(refreshPromises)
    } catch (err) {
      console.error('Failed to refresh running executions:', err)
    }
  }

  // Invalidate the previous case’s requests, streams, and execution data.
  function resetCaseExecutions() {
    generation++
    activeExecutions.value = {}
    executionHistory.value = []
    error.value = null
    for (const id of observations.keys()) unsubscribeFromExecution(id)
  }

  return {
    // State
    availableHunts,
    activeExecutions,
    executionHistory,
    loading,
    error,

    // Getters
    huntsByCategory,
    runningExecutions,
    completedExecutions,
    failedExecutions,

    // Actions
    fetchHunts,
    getHunt,
    executeHunt,
    getExecution,
    getCaseExecutions,
    cancelExecution,
    subscribeToExecution,
    unsubscribeFromExecution,
    clearError,
    removeExecution,
    refreshRunningExecutions,
    resetCaseExecutions,
  }
})
