import { ref, onScopeDispose } from 'vue'
import { observeExecution } from '@/services/observeExecution'
import { pluginService } from '@/services/plugin'

export function usePluginExecution() {
  const execution = ref(null)
  const results = ref([])
  const error = ref(null)
  const cancelling = ref(false)
  let stopObservation
  let generation = 0

  function stop() {
    generation++
    stopObservation?.()
  }

  function observe(id) {
    stop()
    const current = generation
    execution.value = null
    results.value = []
    error.value = null
    let cursor = 0
    stopObservation = observeExecution({
      async refresh(signal) {
        const state = await pluginService.getExecution(id, signal)
        const page = await pluginService.getResults(id, cursor, signal)
        if (current !== generation) return { terminal: true }
        if ((state.revision ?? 0) >= (execution.value?.revision ?? 0)) execution.value = state
        if (page.cursor > cursor) {
          results.value.push(...page.items)
          cursor = page.cursor
        }
        error.value = null
        return {
          terminal: ['completed', 'failed', 'cancelled'].includes(execution.value.status),
          more: !!page.next_cursor,
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
  return { execution, results, error, observe, stop, cancel, cancelling }
}
