import { createHash, webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import { flushPromises } from '@vue/test-utils'
import { pluginService } from '../plugin'
import { huntService } from '../hunt'

vi.mock('../api', () => ({ default: { post: vi.fn() } }))
describe.each(['secure context', 'HTTP context'])('%s', (context) => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal(
      'crypto',
      context === 'secure context'
        ? webcrypto
        : { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) },
    )
    sessionStorage.clear()
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('submits DNS lookups when secure-context crypto APIs are unavailable', async () => {
    vi.stubGlobal('crypto', { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) })
    api.post.mockResolvedValue({ data: { id: 12 } })

    await expect(
      pluginService.executePlugin('DNS Lookup', { domains: ['example.com'] }, 1),
    ).resolves.toEqual({ id: 12 })
    expect(api.post).toHaveBeenCalledWith(
      '/api/plugins/DNS Lookup/execute',
      { domains: ['example.com'], case_id: 1 },
      {
        headers: {
          'Idempotency-Key': expect.stringMatching(
            /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
          ),
        },
      },
    )
  })

  it('recovers an existing SHA-256 identity with canonical Unicode input', async () => {
    localStorage.setItem('access_token', 'test-token')
    const input = JSON.stringify([
      'test-token',
      '/api/plugins/DNS Lookup/execute',
      { case_id: 7, options: { a: ['例え.jp'], z: true } },
    ])
    const identity = 'owlculus:submission:' + createHash('sha256').update(input).digest('hex')
    const key = webcrypto.randomUUID()
    sessionStorage.setItem(identity, key)
    api.post.mockRejectedValueOnce(new Error('Lost response'))

    await expect(
      pluginService.executePlugin('DNS Lookup', { options: { z: true, a: ['例え.jp'] } }, 7),
    ).rejects.toThrow(/retry/i)
    expect(api.post.mock.calls[0][2].headers['Idempotency-Key']).toBe(key)
    expect(Object.keys(sessionStorage)).toEqual([identity])

    api.post.mockResolvedValueOnce({ data: { id: 12 } })
    await pluginService.executePlugin('DNS Lookup', { options: { a: ['例え.jp'], z: true } }, 7)
    expect(api.post.mock.calls[1][2].headers['Idempotency-Key']).toBe(key)
    expect(sessionStorage.length).toBe(0)
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
})
