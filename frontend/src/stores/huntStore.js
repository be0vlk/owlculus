import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { huntService } from '../services/hunt'

export const useHuntStore = defineStore('hunt', () => {
  // State
  const availableHunts = ref([])
  const activeExecutions = ref({})
  const executionHistory = ref([])
  const loading = ref(false)
  const error = ref(null)
  const websocketConnections = ref(new Map())

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
    return Object.values(activeExecutions.value).filter(
      (execution) => execution.status === 'running',
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

      // Add to active executions with full data - ensure reactivity
      activeExecutions.value = {
        ...activeExecutions.value,
        [fullExecution.id]: fullExecution,
      }

      // Also add to execution history
      executionHistory.value.unshift(fullExecution)
      executionHistory.value.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

      // Start WebSocket monitoring
      subscribeToExecution(fullExecution.id)

      return fullExecution
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to execute hunt'
      console.error('Failed to execute hunt:', err)
      throw err
    }
  }

  async function getExecution(executionId, includeSteps = false) {
    try {
      const execution = await huntService.getExecution(executionId, includeSteps)

      // Update active executions
      activeExecutions.value[execution.id] = execution

      return execution
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch execution'
      console.error('Failed to fetch execution:', err)
      throw err
    }
  }

  async function getCaseExecutions(caseId) {
    try {
      const executions = await huntService.getCaseExecutions(caseId)

      // Update execution history
      executionHistory.value = executions

      // Add running/recent executions to active executions
      executions.forEach((execution) => {
        if (execution.status === 'running' || execution.status === 'pending') {
          activeExecutions.value[execution.id] = execution
        }
      })

      return executions
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to fetch case executions'
      console.error('Failed to fetch case executions:', err)
      throw err
    }
  }

  async function loadAllActiveExecutions(cases) {
    try {
      error.value = null

      // Clear existing active executions
      activeExecutions.value = {}

      // Load executions from all accessible cases
      const loadPromises = cases.map(async (caseItem) => {
        try {
          const executions = await huntService.getCaseExecutions(caseItem.id)

          // Add active executions to the store with full details
          const activeExecPromises = executions
            .filter((execution) => execution.status === 'running' || execution.status === 'pending')
            .map(async (execution) => {
              try {
                // Fetch full execution details including steps
                const fullExecution = await huntService.getExecution(execution.id, true)
                activeExecutions.value[fullExecution.id] = fullExecution

                // Subscribe to real-time updates for running executions
                if (fullExecution.status === 'running') {
                  subscribeToExecution(fullExecution.id)
                }

                return fullExecution
              } catch (err) {
                console.error(`Failed to load execution details for ${execution.id}:`, err)
                // Fallback to basic execution data
                activeExecutions.value[execution.id] = execution
                if (execution.status === 'running') {
                  subscribeToExecution(execution.id)
                }
                return execution
              }
            })

          await Promise.all(activeExecPromises)

          return executions
        } catch (err) {
          console.error(`Failed to load executions for case ${caseItem.id}:`, err)
          return []
        }
      })

      const allExecutions = await Promise.all(loadPromises)
      const flatExecutions = allExecutions.flat()

      // Update execution history with recent executions
      executionHistory.value = flatExecutions.sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at),
      )

      return flatExecutions
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load active executions'
      console.error('Failed to load active executions:', err)
      throw err
    }
  }

  async function cancelExecution(executionId) {
    try {
      error.value = null
      const result = await huntService.cancelExecution(executionId)

      // Update execution status
      const execution = activeExecutions.value[executionId]
      if (execution) {
        execution.status = 'cancelled'
        activeExecutions.value[executionId] = execution
      }

      // Close WebSocket connection
      unsubscribeFromExecution(executionId)

      return result
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to cancel execution'
      console.error('Failed to cancel execution:', err)
      throw err
    }
  }

  function subscribeToExecution(executionId) {
    // Don't create duplicate connections
    if (websocketConnections.value.has(executionId)) {
      return
    }

    const onMessage = async (data) => {
      // Handle initial connection message
      if (data.event_type === 'connected') {
        // Ensure we have the execution data
        if (!activeExecutions.value[executionId]) {
          try {
            await getExecution(executionId, true)
          } catch (err) {
            console.error('Failed to load execution data on WebSocket connect:', err)
          }
        }
        return
      }

      // Update execution in store based on WebSocket message
      const execution = activeExecutions.value[executionId]
      if (execution) {
        // Create a new object to ensure reactivity
        const updatedExecution = { ...execution }

        switch (data.event_type) {
          case 'progress':
            updatedExecution.progress = data.progress || execution.progress
            // Update step status if provided
            if (data.step_id && updatedExecution.steps) {
              const stepIndex = updatedExecution.steps.findIndex((s) => s.step_id === data.step_id)
              if (stepIndex !== -1) {
                updatedExecution.steps[stepIndex] = {
                  ...updatedExecution.steps[stepIndex],
                  status: 'running',
                }
              }
            }
            break
          case 'step_complete':
            updatedExecution.progress = data.progress || execution.progress
            // Update step status if provided
            if (data.step_id && updatedExecution.steps) {
              const stepIndex = updatedExecution.steps.findIndex((s) => s.step_id === data.step_id)
              if (stepIndex !== -1) {
                updatedExecution.steps[stepIndex] = {
                  ...updatedExecution.steps[stepIndex],
                  status: 'completed',
                }
              }
            }
            break
          case 'step_failed':
            updatedExecution.progress = data.progress || execution.progress
            // Update step status if provided
            if (data.step_id && updatedExecution.steps) {
              const stepIndex = updatedExecution.steps.findIndex((s) => s.step_id === data.step_id)
              if (stepIndex !== -1) {
                updatedExecution.steps[stepIndex] = {
                  ...updatedExecution.steps[stepIndex],
                  status: 'failed',
                }
              }
            }
            break
          case 'complete': {
            updatedExecution.status = 'completed'
            updatedExecution.progress = 1.0
            updatedExecution.completed_at = new Date().toISOString()

            // Fetch the latest execution details with steps
            try {
              const fullExecution = await getExecution(executionId, true)
              Object.assign(updatedExecution, fullExecution)
            } catch (err) {
              console.error('Failed to fetch completed execution details:', err)
            }

            // Update execution history to include the completed execution
            const historyIndex = executionHistory.value.findIndex((e) => e.id === executionId)
            if (historyIndex !== -1) {
              executionHistory.value[historyIndex] = { ...updatedExecution }
            } else {
              executionHistory.value.unshift({ ...updatedExecution })
            }

            unsubscribeFromExecution(executionId)
            break
          }
          case 'error': {
            updatedExecution.status = 'failed'
            updatedExecution.completed_at = new Date().toISOString()

            // Update execution history
            const errorHistoryIndex = executionHistory.value.findIndex((e) => e.id === executionId)
            if (errorHistoryIndex !== -1) {
              executionHistory.value[errorHistoryIndex] = { ...updatedExecution }
            } else {
              executionHistory.value.unshift({ ...updatedExecution })
            }

            unsubscribeFromExecution(executionId)
            break
          }
        }

        // Force reactivity by replacing the entire object
        activeExecutions.value = {
          ...activeExecutions.value,
          [executionId]: updatedExecution,
        }
      }
    }

    const onError = (error) => {
      console.error(`WebSocket error for execution ${executionId}:`, error)
      // Don't immediately remove on error, let it retry
    }

    huntService
      .createExecutionStream(executionId, onMessage, onError)
      .then((ws) => {
        websocketConnections.value.set(executionId, ws)
      })
      .catch((err) => {
        console.error('Failed to create WebSocket connection:', err)
        error.value = 'Failed to connect to execution stream'
      })
  }

  function unsubscribeFromExecution(executionId) {
    const ws = websocketConnections.value.get(executionId)
    if (ws) {
      huntService.closeExecutionStream(ws)
      websocketConnections.value.delete(executionId)
    }
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
    const runningExecs = runningExecutions.value
    if (runningExecs.length === 0) return

    try {
      const refreshPromises = runningExecs.map(async (execution) => {
        try {
          const updated = await huntService.getExecution(execution.id, true)

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

  // Cleanup all WebSocket connections
  function cleanup() {
    websocketConnections.value.forEach((ws) => {
      huntService.closeExecutionStream(ws)
    })
    websocketConnections.value.clear()
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
    loadAllActiveExecutions,
    cancelExecution,
    subscribeToExecution,
    unsubscribeFromExecution,
    clearError,
    removeExecution,
    refreshRunningExecutions,
    cleanup,
  }
})
