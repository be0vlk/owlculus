// A single in-flight durable read and a single retry timer per open view. Stream
// bursts coalesce into one refresh; reconnects never submit execution work.
export function observeExecution({ refresh, openStream, closeStream, onError }) {
  const controller = new AbortController()
  let stopped = false
  let timer
  let socket
  let opening = false
  let polling = false
  let refreshPending = false
  let cursor
  let delay = 1000

  function stop() {
    stopped = true
    clearTimeout(timer)
    controller.abort()
    closeStream?.(socket)
    socket = null
  }

  function changed(event) {
    if (stopped) return
    cursor = event.cursor || cursor
    clearTimeout(timer)
    if (polling) refreshPending = true
    else poll()
  }

  async function connect() {
    if (stopped || socket || opening || !openStream) return
    opening = true
    try {
      const next = await openStream(
        changed,
        () => {
          if (stopped) return
          closeStream?.(socket)
          socket = null
          onError('Live progress interrupted; checking retained investigation results')
        },
        cursor,
      )
      if (stopped) closeStream?.(next)
      else socket = next
    } catch {
      // The durable polling path remains available during token/Redis outages.
      if (!stopped) onError('Live progress unavailable; checking retained investigation results')
    } finally {
      opening = false
    }
  }

  async function poll() {
    if (stopped || polling) return
    polling = true
    let more = false
    try {
      const state = await refresh(controller.signal)
      if (stopped) return
      more = state.more
      if (state.terminal && !more) {
        stop()
        return
      }
      connect()
    } catch (failure) {
      if (stopped) return
      onError(failure.response?.data?.detail || 'Could not refresh investigation results; retrying')
      if ([401, 403, 404].includes(failure.response?.status)) {
        stop()
        return
      }
    } finally {
      polling = false
      if (!stopped) {
        clearTimeout(timer)
        timer = setTimeout(poll, more || refreshPending ? 0 : delay)
        refreshPending = false
        delay = Math.min(delay * 1.5, 10000)
      }
    }
  }
  poll()
  return stop
}
