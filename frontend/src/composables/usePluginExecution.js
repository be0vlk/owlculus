import { ref, onScopeDispose } from 'vue'
import { pluginService } from '@/services/plugin'

export function usePluginExecution() {
  const execution = ref(null)
  const results = ref([])
  const error = ref(null)
  let controller
  let timer
  let generation = 0

  function stop() {
    generation++
    controller?.abort()
    clearTimeout(timer)
  }

  function observe(id) {
    stop()
    const current = generation
    controller = new AbortController()
    const signal = controller.signal
    execution.value = null
    results.value = []
    error.value = null
    let cursor = 0
    let delay = 1000
    async function poll() {
      try {
        const state = await pluginService.getExecution(id, signal)
        const page = await pluginService.getResults(id, cursor, signal)
        if (current !== generation) return
        execution.value = state
        results.value.push(...page.items)
        cursor = page.cursor
        error.value = null
        const terminal = ['completed', 'failed', 'cancelled'].includes(state.status)
        if (page.next_cursor || !terminal) {
          timer = setTimeout(poll, page.next_cursor ? 0 : delay)
          delay = Math.min(delay * 1.5, 10000)
        }
      } catch (failure) {
        if (current !== generation) return
        error.value = failure.response?.data?.detail || failure.message
        if (![401, 403, 404].includes(failure.response?.status)) {
          timer = setTimeout(poll, delay)
          delay = Math.min(delay * 2, 10000)
        }
      }
    }
    poll()
  }

  onScopeDispose(stop)
  return { execution, results, error, observe, stop }
}
