import { onScopeDispose, ref, watch } from 'vue'
import { pluginService } from '@/services/plugin'

// A refresh replaces the loaded range atomically, including records inserted since
// the last read. The API cursor is an exclusive execution-ID boundary.
export function usePluginHistory(caseId) {
  const items = ref([])
  const nextCursor = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const accessDenied = ref(false)
  let controller
  let lastMore = false

  async function load(more = false) {
    if (more && (loading.value || nextCursor.value == null)) return
    lastMore = more
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    const owner = caseId()
    const current = () => !signal.aborted && owner === caseId()
    const oldest = items.value.length ? Math.min(...items.value.map((item) => item.id)) : null
    const wasComplete = items.value.length > 0 && nextCursor.value == null
    let cursor = more ? nextCursor.value : 0
    const records = new Map(more ? items.value.map((item) => [item.id, item]) : [])
    loading.value = true
    error.value = null
    try {
      const visited = new Set()
      do {
        if (visited.has(cursor)) throw new Error('Plugin history returned a repeated cursor.')
        visited.add(cursor)
        const page = await pluginService.getHistory(owner, cursor, signal)
        if (!current()) return
        page.items.forEach((item) => records.set(item.id, item))
        cursor = page.next_cursor
        // Refresh through the previous oldest record (or through the end when
        // all history was loaded); a new first page must not hide older pages.
      } while (!more && cursor != null && (wasComplete || (oldest != null && cursor > oldest)))
      if (!current()) return
      items.value = [...records.values()]
      nextCursor.value = cursor
      accessDenied.value = false
    } catch (failure) {
      if (current()) {
        if ([401, 403, 404].includes(failure.response?.status)) {
          items.value = []
          nextCursor.value = null
          accessDenied.value = true
          lastMore = false
        }
        error.value = failure.response?.data?.detail || failure.message
      }
    } finally {
      if (current()) loading.value = false
    }
  }

  watch(
    caseId,
    () => {
      controller?.abort()
      items.value = []
      nextCursor.value = null
      error.value = null
      accessDenied.value = false
      loading.value = false
      if (caseId()) load()
    },
    { immediate: true, flush: 'sync' },
  )
  onScopeDispose(() => controller?.abort())
  return { items, nextCursor, loading, error, accessDenied, load, retry: () => load(lastMore) }
}
