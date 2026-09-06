import { observeExecution } from '@/services/observeExecution'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { huntService } from '../services/hunt'

export const useHuntStore = defineStore('hunt', () => {
  let generation = 0
  // State
  const availableHunts = ref([])
  const records = ref({})
  const historyIds = ref([])
  const fieldRevisions = new Map()
  let workflowCaseId = null
  const activeExecutions = computed(() => records.value)
  const executionHistory = computed(() =>
    historyIds.value.map((id) => records.value[id]).filter(Boolean),
  )
  const isActive = (execution) => ['pending', 'running', 'cancelling'].includes(execution?.status)

  // Summaries and acknowledgements are partial. Only a requested step read can clear steps.
  function reconcile(response, { includeSteps = false } = {}) {
    workflowCaseId ??= response.case_id
    const id = response.id ?? response.execution_id
    const previous = records.value[id]
    const incoming = Object.fromEntries(
      Object.entries(response).filter(([, value]) => value !== undefined),
    )
    incoming.id = id
    delete incoming.execution_id
    delete incoming.message
    if (incoming.hunt_display_name != null || incoming.hunt_category != null || incoming.hunt) {
      incoming.hunt = { ...incoming.hunt }
      if (incoming.hunt_display_name != null)
        incoming.hunt.display_name = incoming.hunt_display_name
      if (incoming.hunt_category != null) incoming.hunt.category = incoming.hunt_category
      if (incoming.hunt.display_name != null)
        incoming.hunt_display_name = incoming.hunt.display_name
      if (incoming.hunt.category != null) incoming.hunt_category = incoming.hunt.category
    }
    if (!includeSteps || !Object.hasOwn(incoming, 'steps')) delete incoming.steps
    else incoming.steps ??= []

    const knownRevision = previous?.revision ?? 0
    const revision = incoming.revision ?? 0
    if (revision < knownRevision) return previous
    const enrichOnly = previous && knownRevision > 0 && revision === knownRevision
    if (previous && !isActive(previous) && isActive(incoming) && revision <= knownRevision) {
      delete incoming.status
    }
    // Retained fields may predate the record revision when a partial response advanced it.
    const suppliedRevisions = fieldRevisions.get(id) ?? {}
    const merged = { ...previous }
    for (const [key, value] of Object.entries(incoming)) {
      if (key === 'hunt') {
        merged.hunt = enrichOnly ? { ...value, ...previous.hunt } : { ...previous?.hunt, ...value }
      } else if (
        !enrichOnly ||
        (suppliedRevisions[key] ?? 0) < revision ||
        merged[key] == null ||
        (key === 'steps' && merged.steps.length === 0 && value.length > 0)
      ) {
        merged[key] = value
        suppliedRevisions[key] = revision
      }
    }
    fieldRevisions.set(id, suppliedRevisions)
    records.value[id] = merged
    return records.value[id]
  }

  function rememberHistory(id) {
    historyIds.value = [...new Set([id, ...historyIds.value])].sort(
      (a, b) => new Date(records.value[b].created_at) - new Date(records.value[a].created_at),
    )
  }
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

      if (request !== generation) return execution
      reconcile(execution)
      rememberHistory(execution.id)
      // Accepted identity remains available even if the richer read fails.
      try {
        await getExecution(execution.id, true)
      } catch (err) {
        console.error('Failed to fetch full execution details:', err)
      }
      if (request !== generation) return execution
      const current = records.value[execution.id]
      if (isActive(current)) subscribeToExecution(current.id)
      return current
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

      return request === generation ? reconcile(execution, { includeSteps }) : execution
    } catch (err) {
      if (request === generation)
        error.value = err.response?.data?.detail || 'Failed to fetch execution'
      console.error('Failed to fetch execution:', err)
      throw err
    }
  }

  async function getCaseExecutions(caseId) {
    if (String(caseId) !== String(workflowCaseId)) {
      resetCaseExecutions()
      workflowCaseId = caseId
    }
    const request = generation
    if (!caseId) return []
    try {
      const executions = await huntService.getCaseExecutions(caseId)
      if (request !== generation) return []
      executions.forEach((execution) => reconcile(execution))
      historyIds.value = [...new Set(executions.map((execution) => execution.id))]
      await Promise.all(
        executions
          .filter((execution) => isActive(records.value[execution.id]))
          .map(async (execution) => {
            try {
              await getExecution(execution.id, true)
            } catch {
              // The list response still provides usable progress if details fail.
            }
            if (request === generation) subscribeToExecution(execution.id)
          }),
      )
      return request === generation ? executionHistory.value : []
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

      const execution = reconcile({ ...result, id: result.execution_id ?? executionId })
      if (isActive(execution)) subscribeToExecution(executionId)
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
        const latest = reconcile(execution, { includeSteps: true })
        error.value = null
        const terminal = !isActive(latest)
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
    delete records.value[executionId]
    fieldRevisions.delete(executionId)
    historyIds.value = historyIds.value.filter((id) => id !== executionId)
    unsubscribeFromExecution(executionId)
  }

  // Invalidate the previous case’s requests, streams, and execution data.
  function resetCaseExecutions() {
    generation++
    records.value = {}
    fieldRevisions.clear()
    historyIds.value = []
    workflowCaseId = null
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
    resetCaseExecutions,
  }
})
