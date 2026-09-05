import api from './api'

// Keep unresolved runs across navigation. Observation never calls this module.
const pending = new Map()

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    )
  }
  return value
}

export async function submitExecution(endpoint, payload) {
  const identity = JSON.stringify([endpoint, canonical(payload)])
  const key = pending.get(identity) || crypto.randomUUID()
  pending.set(identity, key)
  try {
    const response = await api.post(endpoint, payload, { headers: { 'Idempotency-Key': key } })
    pending.delete(identity)
    return response.data
  } catch (failure) {
    const status = failure.response?.status
    if (status >= 400 && status < 500 && ![408, 429].includes(status)) pending.delete(identity)
    const guidance = {
      409: 'This retry conflicts with an earlier submission. Start a new run with the intended input.',
      429: 'Execution capacity is full. Wait for work to finish, then retry.',
      503: 'Execution acceptance is unavailable. Retry with the same input when services recover.',
    }
    const detail = failure.response?.data?.detail
    const message =
      guidance[status] ||
      (!status || status >= 500 || status === 408
        ? 'The submission response was uncertain. Retry with the same input to recover this run safely.'
        : typeof detail === 'string'
          ? detail
          : failure.message)
    const error = new Error(message, { cause: failure })
    error.response = failure.response
    throw error
  }
}
