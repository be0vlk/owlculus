import { ref, onScopeDispose } from 'vue'
import { observeExecution } from '@/services/observeExecution'
import { pluginService } from '@/services/plugin'

export function usePluginExecution() {
  const execution = ref(null)
  const results = ref([])
  const error = ref(null)
  const cancelling = ref(false)
  const retrievalLoading = ref(false)
  const retrievalComplete = ref(false)
  let cursor = 0
  let selectedId
  let stopObservation
  let generation = 0

  function stop() {
    generation++
    stopObservation?.()
  }

  function clearInaccessibleContent() {
    stop()
    results.value = []
    retrievalComplete.value = false
    retrievalLoading.value = false
    if (execution.value) execution.value = { ...execution.value, parameters: {}, error: null }
    error.value = 'Could not access investigation results. Check access and retry.'
  }

  function observe(id, resume = false) {
    stop()
    const current = generation
    selectedId = id
    if (!resume) {
      execution.value = null
      results.value = []
      cursor = 0
    }
    retrievalLoading.value = true
    retrievalComplete.value = false
    error.value = null
    stopObservation = observeExecution({
      async refresh(signal) {
        try {
          const state = await pluginService.getExecution(id, signal)
          if (current !== generation) return { terminal: true }
          if ((state.revision ?? 0) >= (execution.value?.revision ?? 0)) execution.value = state
          const page = await pluginService.getResults(id, cursor, signal)
          if (current !== generation) return { terminal: true }
          if (page.cursor > cursor) {
            results.value.push(...page.items)
            cursor = page.cursor
          }
          const terminal = ['completed', 'failed', 'cancelled'].includes(execution.value.status)
          retrievalComplete.value = terminal && page.next_cursor == null
          retrievalLoading.value = page.next_cursor != null
          error.value = null
          return { terminal, more: page.next_cursor != null }
        } catch (failure) {
          if (current === generation) {
            retrievalLoading.value = false
            retrievalComplete.value = false
            if ([401, 403, 404].includes(failure.response?.status)) clearInaccessibleContent()
          }
          throw failure
        }
      },
      openStream: pluginService.createExecutionStream
        ? (...args) => pluginService.createExecutionStream(id, ...args)
        : undefined,
      closeStream: pluginService.closeExecutionStream,
      onError(message) {
        if (current === generation) error.value = message
      },
    })
  }

  async function cancel() {
    if (!execution.value || cancelling.value) return
    const current = generation
    const id = execution.value.id
    cancelling.value = true
    try {
      const state = await pluginService.cancelExecution(id)
      if (
        current === generation &&
        (!execution.value?.revision || state.revision >= execution.value.revision)
      )
        execution.value = state
    } catch (failure) {
      if (current === generation) error.value = failure.response?.data?.detail || failure.message
    } finally {
      cancelling.value = false
    }
  }

  onScopeDispose(stop)
  return {
    clearInaccessibleContent,
    execution,
    results,
    error,
    retrievalLoading,
    retrievalComplete,
    retry: () => observe(selectedId, true),
    observe,
    stop,
    cancel,
    cancelling,
  }
}
