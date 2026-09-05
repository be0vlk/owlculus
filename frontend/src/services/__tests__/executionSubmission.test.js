import { beforeEach, expect, it, vi } from 'vitest'
import api from '../api'
import { pluginService } from '../plugin'
import { huntService } from '../hunt'

vi.mock('../api', () => ({ default: { post: vi.fn() } }))
beforeEach(() => vi.clearAllMocks())

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
