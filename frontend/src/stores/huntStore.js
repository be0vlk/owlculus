import { observeExecution } from '@/services/observeExecution'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { huntService } from '../services/hunt'

export const useHuntStore = defineStore('hunt', () => {
  let generation = 0
  let historyRequest = 0
  let workflow = null
  const reads = new Map()
  const deniedExecutionIds = new Set()
  const terminalDetailRevisions = new Map()
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
  function reconcile(response, { includeSteps = false, summary = false } = {}) {
    if (
      workflowCaseId != null &&
      response.case_id != null &&
      String(workflowCaseId) !== String(response.case_id)
    )
      return null
    workflowCaseId ??= response.case_id
    const id = response.id ?? response.execution_id
    if (deniedExecutionIds.has(String(id))) return null
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
    if (summary && previous) {
      // History can fill presentation gaps, but cannot replace durable or retained legacy data.
      for (const key of Object.keys(incoming)) {
        if (key === 'hunt') incoming.hunt = { ...incoming.hunt, ...previous.hunt }
        else if (previous[key] != null) delete incoming[key]
      }
    }
    if (!summary && revision < knownRevision) return previous
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
    if (
      includeSteps &&
      response.steps !== undefined &&
      !isActive(response) &&
      response.status &&
      revision >= (merged.revision ?? 0)
    ) {
      terminalDetailRevisions.set(id, merged.revision ?? 0)
    }
    return records.value[id]
  }

  function rememberHistory(ids) {
    historyIds.value = [...new Set([...ids, ...historyIds.value])].sort(
      (a, b) => new Date(records.value[b].created_at) - new Date(records.value[a].created_at),
    )
  }
  const loading = ref(false)
  const readErrors = ref({})
  const actionError = ref(null)
  const visibleError = computed(
    () => actionError.value || Object.values(readErrors.value).find(Boolean),
  )
  const needsObservation = (record) =>
    record &&
    (isActive(record) || terminalDetailRevisions.get(record.id) !== (record.revision ?? 0))

  async function read(operation, executionId = null) {
    const controller = new AbortController()
    reads.set(controller, executionId)
    try {
      return await operation(controller.signal)
    } finally {
      reads.delete(controller)
    }
  }

  function openWorkflow({ caseId, executionId = null }) {
    const sameCase = String(workflowCaseId) === String(caseId)
    invalidateWorkflow(!sameCase)
    workflowCaseId = caseId
    const owner = generation
    const handle = {
      isCurrent: () => owner === generation,
      async refresh() {
        if (!handle.isCurrent() || !caseId) return
        if (executionId != null) return getExecution(executionId, true)
        await Promise.all([fetchHunts(), getCaseExecutions(caseId)])
      },
      release() {
        if (handle.isCurrent()) invalidateWorkflow(true)
      },
    }
    workflow = handle
    return handle
  }
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
    const request = generation
    try {
      loading.value = true
      readErrors.value['catalog'] = null
      const hunts = await read((signal) => huntService.getHunts(signal))
      if (request !== generation) return
      availableHunts.value = hunts
    } catch (err) {
      if (request !== generation) return
      readErrors.value['catalog'] = err.response?.data?.detail || 'Failed to fetch hunts'
      console.error('Failed to fetch hunts:', err)
      throw err
    } finally {
      if (request === generation) loading.value = false
    }
  }

  async function getHunt(huntId) {
    const request = generation
    try {
      const hunt = await read((signal) => huntService.getHunt(huntId, signal))
      return hunt
    } catch (err) {
      if (request === generation)
        readErrors.value[`hunt-${huntId}`] = err.response?.data?.detail || 'Failed to fetch hunt'
      console.error('Failed to fetch hunt:', err)
      throw err
    }
  }

  async function executeHunt(huntId, caseId, parameters) {
    const request = generation
    try {
      actionError.value = null
      const execution = await huntService.executeHunt(huntId, caseId, parameters)

      if (request !== generation) return execution
      reconcile(execution)
      rememberHistory([execution.id])
      // Accepted identity remains available even if the richer read fails.
      try {
        await getExecution(execution.id, true)
      } catch (err) {
        console.error('Failed to fetch full execution details:', err)
      }
      if (request !== generation) return execution
      const current = records.value[execution.id]
      if (needsObservation(current)) subscribeToExecution(current.id)
      return current
    } catch (err) {
      if (request === generation)
        actionError.value = err.response?.data?.detail || 'Failed to execute hunt'
      console.error('Failed to execute hunt:', err)
      throw err
    }
  }

  async function getExecution(executionId, includeSteps = false) {
    const request = generation
    try {
      const execution = await read(
        (signal) => huntService.getExecution(executionId, includeSteps, signal),
        executionId,
      )

      if (request !== generation) return execution
      const latest = reconcile(execution, { includeSteps })
      if (!latest) {
        removeExecution(executionId)
        return execution
      }
      readErrors.value[executionId] = null
      if (workflow && needsObservation(latest)) subscribeToExecution(executionId)
      else if (!needsObservation(latest)) unsubscribeFromExecution(executionId)
      return latest
    } catch (err) {
      if (request === generation && !deniedExecutionIds.has(String(executionId))) {
        if (isAccessFailure(err)) removeExecution(executionId)
        else if (
          workflow &&
          (!records.value[executionId] || needsObservation(records.value[executionId]))
        )
          subscribeToExecution(executionId)
        readErrors.value[executionId] =
          err.response?.data?.detail || err.message || 'Failed to fetch execution'
      }
      console.error('Failed to fetch execution:', err)
      throw err
    }
  }

  const isAccessFailure = (err) => [401, 403, 404].includes(err.response?.status)
  const summaryChanged = (summary, record) =>
    record &&
    ['status', 'progress', 'started_at', 'completed_at'].some(
      (key) => Object.hasOwn(summary, key) && summary[key] !== record[key],
    )

  async function getCaseExecutions(caseId) {
    if (String(caseId) !== String(workflowCaseId)) {
      resetCaseExecutions()
      workflowCaseId = caseId
    }
    const request = generation
    const historyRead = ++historyRequest
    const current = () => request === generation && historyRead === historyRequest
    if (!caseId) return []
    readErrors.value['history'] = null
    try {
      const executions = await read((signal) => huntService.getCaseExecutions(caseId, signal))
      if (!current()) return []
      const detailIds = new Set()
      executions.forEach((execution) => {
        if (deniedExecutionIds.has(String(execution.id))) return
        if (summaryChanged(execution, records.value[execution.id]) || isActive(execution))
          detailIds.add(execution.id)
        reconcile(execution, { summary: true })
      })
      rememberHistory(executions.map((execution) => execution.id).filter((id) => records.value[id]))
      await Promise.all(
        [...detailIds].map(async (id) => {
          try {
            const detail = await read((signal) => huntService.getExecution(id, true, signal), id)
            if (!current() || deniedExecutionIds.has(String(id))) return
            readErrors.value[id] = null
            if (!reconcile(detail, { includeSteps: true })) removeExecution(id)
          } catch (err) {
            if (!current() || deniedExecutionIds.has(String(id))) return
            if (isAccessFailure(err)) removeExecution(id)
            readErrors.value[id] =
              err.response?.data?.detail || err.message || 'Failed to fetch execution'
          }
          if (current()) {
            if (needsObservation(records.value[id])) subscribeToExecution(id)
            else unsubscribeFromExecution(id)
          }
        }),
      )
      return current() ? executionHistory.value : []
    } catch (err) {
      if (!current()) return []
      if (isAccessFailure(err)) resetCaseExecutions()
      readErrors.value['history'] = err.response?.data?.detail || 'Failed to fetch case executions'
      throw err
    }
  }

  async function cancelExecution(executionId) {
    const request = generation
    try {
      actionError.value = null
      const result = await huntService.cancelExecution(executionId)
      if (request !== generation) return result

      const execution = reconcile({ ...result, id: result.execution_id ?? executionId })
      if (needsObservation(execution)) subscribeToExecution(executionId)
      else unsubscribeFromExecution(executionId)

      return result
    } catch (err) {
      if (request === generation)
        actionError.value = err.response?.data?.detail || 'Failed to cancel execution'
      console.error('Failed to cancel execution:', err)
      throw err
    }
  }

  function subscribeToExecution(executionId) {
    if (observations.has(executionId) || deniedExecutionIds.has(String(executionId))) return
    const request = generation
    const observation = { stop: null }
    observations.set(executionId, observation)
    const current = () => request === generation && observations.get(executionId) === observation
    observation.stop = observeExecution({
      async refresh(signal) {
        let execution
        try {
          execution = await huntService.getExecution(executionId, true, signal)
        } catch (err) {
          if (current() && isAccessFailure(err)) {
            readErrors.value[executionId] = err.response?.data?.detail || 'Execution unavailable'
            removeExecution(executionId)
          }
          throw err
        }
        if (!current()) return { terminal: true }
        const latest = reconcile(execution, { includeSteps: true })
        readErrors.value[executionId] = null
        if (!latest) removeExecution(executionId)
        const terminal = !needsObservation(latest)
        if (terminal) observations.delete(executionId)
        return { terminal }
      },
      openStream: (...args) => huntService.createExecutionStream(executionId, ...args),
      closeStream: huntService.closeExecutionStream,
      onError(message) {
        if (current()) readErrors.value[executionId] = message
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
    readErrors.value = {}
    actionError.value = null
  }

  function removeExecution(executionId) {
    // A denied identity stays unavailable until a newly authorized workflow opens.
    deniedExecutionIds.add(String(executionId))
    for (const [controller, id] of reads) {
      if (String(id) === String(executionId)) controller.abort()
    }
    delete records.value[executionId]
    fieldRevisions.delete(executionId)
    terminalDetailRevisions.delete(executionId)
    historyIds.value = historyIds.value.filter((id) => id !== executionId)
    unsubscribeFromExecution(executionId)
  }

  function invalidateWorkflow(clearRecords) {
    generation++
    workflow = null
    deniedExecutionIds.clear()
    for (const controller of reads.keys()) controller.abort()
    reads.clear()
    for (const id of observations.keys()) unsubscribeFromExecution(id)
    if (clearRecords) {
      records.value = {}
      fieldRevisions.clear()
      terminalDetailRevisions.clear()
      historyIds.value = []
    }
    workflowCaseId = null
    loading.value = false
    readErrors.value = {}
    actionError.value = null
  }

  function resetCaseExecutions() {
    invalidateWorkflow(true)
  }

  return {
    // State
    availableHunts,
    activeExecutions,
    executionHistory,
    loading,
    error: visibleError,

    // Getters
    huntsByCategory,
    runningExecutions,
    completedExecutions,
    failedExecutions,

    // Actions
    openWorkflow,
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
