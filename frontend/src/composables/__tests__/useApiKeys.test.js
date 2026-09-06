import { afterEach, expect, it, vi } from 'vitest'
import api from '@/services/api'
import { useApiKeys } from '../useApiKeys'

vi.mock('@/services/api', () => ({ default: { put: vi.fn(), delete: vi.fn() } }))
afterEach(() => vi.restoreAllMocks())

it.each([
  ['addApiKey', 'put', 'add'],
  ['updateApiKey', 'put', 'update'],
  ['deleteApiKey', 'delete', 'delete'],
])(
  '%s preserves the request error, display message, and resets pending state',
  async (action, method, verb) => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const keys = useApiKeys()
    keys.newKeyForm.value = { provider: 'custom', name: 'Test', api_key: 'test-key' }
    keys.editKeyForm.value = { provider: 'custom', name: 'Test', api_key: '' }
    keys.showAddDialog.value = action === 'addApiKey'

    const failure = new Error('Request failed')
    failure.response = { data: { detail: 'Provider is unavailable' } }
    api[method].mockRejectedValue(failure)
    await expect(keys[action]('custom')).rejects.toMatchObject({
      message: 'Provider is unavailable',
      cause: failure,
    })
    expect(keys.saving.value).toBe(false)
    expect(keys.deleting.value).toBe(false)

    const offline = new Error('Network unavailable')
    api[method].mockRejectedValue(offline)
    await expect(keys[action]('custom')).rejects.toMatchObject({
      message: `Failed to ${verb} API key`,
      cause: offline,
    })
    expect(keys.saving.value).toBe(false)
    expect(keys.deleting.value).toBe(false)
  },
)
