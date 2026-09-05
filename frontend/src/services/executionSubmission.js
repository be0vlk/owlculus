import api from './api'
import { authService } from './auth'

// Store only a digest and random key, never credentials or investigation input.
const pending = new Map()
const active = new Set()

function readKey(identity) {
  try {
    return sessionStorage.getItem(identity) || pending.get(identity)
  } catch {
    return pending.get(identity)
  }
}

function writeKey(identity, key) {
  if (key) pending.set(identity, key)
  else pending.delete(identity)
  try {
    if (key) sessionStorage.setItem(identity, key)
    else sessionStorage.removeItem(identity)
  } catch {
    // Browser storage restrictions still permit retries within this page.
  }
}

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
  const input = JSON.stringify([authService.getCurrentToken(), endpoint, canonical(payload)])
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input))
  const identity =
    'owlculus:submission:' +
    Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  const remembered = readKey(identity)
  const key = remembered && !active.has(remembered) ? remembered : crypto.randomUUID()
  active.add(key)
  writeKey(identity, key)
  try {
    const response = await api.post(endpoint, payload, { headers: { 'Idempotency-Key': key } })
    if (readKey(identity) === key) writeKey(identity, null)
    return response.data
  } catch (failure) {
    const status = failure.response?.status
    if (status >= 400 && status < 500 && ![408, 429].includes(status)) {
      if (readKey(identity) === key) writeKey(identity, null)
    } else {
      writeKey(identity, key)
    }
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
  } finally {
    active.delete(key)
  }
}
