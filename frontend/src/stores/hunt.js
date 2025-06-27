import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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
    availableHunts.value.forEach(hunt => {
      if (!categorized[hunt.category]) {
        categorized[hunt.category] = []
      }
      categorized[hunt.category].push(hunt)
    })
    return categorized
  })

  const runningExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter(
      execution => execution.status === 'running'
    )
  })

  const completedExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter(
      execution => execution.status === 'completed' || execution.status === 'partial'
    )
  })

  const failedExecutions = computed(() => {
    return Object.values(activeExecutions.value).filter(
      execution => execution.status === 'failed'
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
      
      // Add to active executions
      activeExecutions.value[execution.id] = execution
      
      // Start WebSocket monitoring
      subscribeToExecution(execution.id)
      
      return execution
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
      executions.forEach(execution => {
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
          
          // Add active executions to the store
          executions.forEach(execution => {
            if (execution.status === 'running' || execution.status === 'pending') {
              activeExecutions.value[execution.id] = execution
              // Subscribe to real-time updates for running executions
              if (execution.status === 'running') {
                subscribeToExecution(execution.id)
              }
            }
          })
          
          return executions
        } catch (err) {
          console.error(`Failed to load executions for case ${caseItem.id}:`, err)
          return []
        }
      })
      
      const allExecutions = await Promise.all(loadPromises)
      const flatExecutions = allExecutions.flat()
      
      // Update execution history with recent executions
      executionHistory.value = flatExecutions.sort((a, b) => 
        new Date(b.created_at) - new Date(a.created_at)
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

    const onMessage = (data) => {
      console.log('Hunt execution update:', data)
      
      // Update execution in store based on WebSocket message
      const execution = activeExecutions.value[executionId]
      if (execution) {
        switch (data.event_type) {
          case 'progress':
            execution.progress = data.progress || execution.progress
            break
          case 'step_complete':
            execution.progress = data.progress || execution.progress
            break
          case 'step_failed':
            execution.progress = data.progress || execution.progress
            break
          case 'complete':
            execution.status = 'completed'
            execution.progress = 1.0
            execution.completed_at = new Date().toISOString()
            unsubscribeFromExecution(executionId)
            break
          case 'error':
            execution.status = 'failed'
            execution.completed_at = new Date().toISOString()
            unsubscribeFromExecution(executionId)
            break
        }
        
        activeExecutions.value[executionId] = { ...execution }
      }
    }

    const onError = (error) => {
      console.error(`WebSocket error for execution ${executionId}:`, error)
      // Don't immediately remove on error, let it retry
    }

    try {
      const ws = huntService.createExecutionStream(executionId, onMessage, onError)
      websocketConnections.value.set(executionId, ws)
    } catch (err) {
      console.error('Failed to create WebSocket connection:', err)
    }
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
    cleanup
  }
})