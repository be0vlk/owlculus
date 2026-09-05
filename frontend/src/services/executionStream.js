import api from './api'

// One capability per connection. Only revision/link notifications travel here;
// typed result payloads continue through the authorized durable result endpoints.
export async function createExecutionStream(kind, id, onMessage, onError, cursor) {
  const response = await api.post('/api/auth/websocket-token', { execution_id: id, kind })
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = import.meta.env.VITE_WS_BASE_URL || `${protocol}//${window.location.host}`
  const query =
    `token=${encodeURIComponent(response.data.token)}` +
    (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '')
  const ws = new WebSocket(`${base}/api/${kind}s/executions/${id}/stream?${query}`)
  let revision = -1
  ws.onmessage = ({ data }) => {
    if (data === 'pong' || data === 'ping') return
    try {
      const event = JSON.parse(data)
      if (event.event_type !== 'resync' && event.revision <= revision) return
      revision = Math.max(revision, event.revision ?? -1)
      onMessage(event)
    } catch {
      onError?.(new Error('Could not refresh investigation progress'))
    }
  }
  ws.onerror = () => onError?.(new Error('Live progress interrupted; checking retained results'))
  ws.onclose = () => onError?.(new Error('Live progress ended; checking retained results'))
  return ws
}

export function closeExecutionStream(ws) {
  if (!ws) return
  ws.onmessage = ws.onerror = ws.onclose = null
  if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) ws.close()
}
