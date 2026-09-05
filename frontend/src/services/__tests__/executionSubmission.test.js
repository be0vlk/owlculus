import { webcrypto } from 'node:crypto'
import { beforeEach, expect, it, vi } from 'vitest'
import api from '../api'
import { flushPromises } from '@vue/test-utils'
import { pluginService } from '../plugin'
import { huntService } from '../hunt'

vi.mock('../api', () => ({ default: { post: vi.fn() } }))
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('crypto', webcrypto)
  sessionStorage.clear()
})

it.each(['plugin', 'hunt'])(
  'retains a %s key after an uncertain response and changes it for a rerun',
  async (kind) => {
    const submit =
      kind === 'plugin'
        ? () => pluginService.executePlugin('Example', { query: 'owl' }, 1)
        : () => huntService.executeHunt(1, 1, { query: 'owl' })
    api.post.mockRejectedValueOnce(new Error('Network Error'))
    await expect(submit()).rejects.toThrow(/retry/i)
    const firstKey = api.post.mock.calls[0][2].headers['Idempotency-Key']
    api.post.mockResolvedValue({ data: { id: 12 } })
    await submit()
    expect(api.post.mock.calls[1][2].headers['Idempotency-Key']).toBe(firstKey)
    await submit()
    expect(api.post.mock.calls[2][2].headers['Idempotency-Key']).not.toBe(firstKey)
  },
)

it.each([409, 429, 503])('provides actionable feedback for HTTP %s', async (status) => {
  api.post.mockRejectedValueOnce({ response: { status, data: {} } })
  await expect(pluginService.executePlugin('Example', {}, status)).rejects.toThrow(
    status === 409 ? /new run/i : /retry/i,
  )
})

it('gives simultaneous deliberate submissions distinct identities', async () => {
  const resolve = []
  api.post.mockImplementation(
    () =>
      new Promise((done) => {
        resolve.push(done)
      }),
  )
  const first = pluginService.executePlugin('Concurrent', {}, 1)
  const second = pluginService.executePlugin('Concurrent', {}, 1)
  await vi.waitFor(() => expect(api.post).toHaveBeenCalledTimes(2))
  expect(api.post.mock.calls[0][2].headers['Idempotency-Key']).not.toBe(
    api.post.mock.calls[1][2].headers['Idempotency-Key'],
  )
  resolve.forEach((done, index) => done({ data: { id: index + 1 } }))
  await Promise.all([first, second])
})

it('recovers the key after reloading and isolates a different login', async () => {
  localStorage.setItem('access_token', 'first-user-token')
  api.post.mockRejectedValueOnce(new Error('Lost response'))
  await expect(
    pluginService.executePlugin('Reload', { query: 'private input' }, 7),
  ).rejects.toThrow(/retry/i)
  const key = api.post.mock.calls[0][2].headers['Idempotency-Key']
  expect(JSON.stringify(sessionStorage)).not.toContain('private input')
  expect(JSON.stringify(sessionStorage)).not.toContain('first-user-token')
  vi.resetModules()
  const { pluginService: reloaded } = await import('../plugin')
  api.post.mockResolvedValue({ data: { id: 19 } })
  await reloaded.executePlugin('Reload', { query: 'private input' }, 7)
  expect(api.post.mock.calls[1][2].headers['Idempotency-Key']).toBe(key)
  localStorage.setItem('access_token', 'different-user-token')
  await reloaded.executePlugin('Reload', { query: 'private input' }, 7)
  expect(api.post.mock.calls[2][2].headers['Idempotency-Key']).not.toBe(key)
  localStorage.clear()
  await flushPromises()
})
