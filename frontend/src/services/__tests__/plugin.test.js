import { beforeEach, expect, it, vi } from 'vitest'
import api from '../api'
import { pluginService } from '../plugin'

vi.mock('../api', () => ({ default: { post: vi.fn() } }))
beforeEach(() => vi.clearAllMocks())

it.each([false, true])(
  'uses application context over plugin parameters when saving is %s',
  async (save) => {
    api.post.mockResolvedValue({ data: { id: 12, status: 'queued' } })
    await pluginService.executePlugin('Example', { case_id: 999, save_to_case: save }, 7)
    expect(api.post).toHaveBeenCalledWith(
      '/api/plugins/Example/execute',
      {
        case_id: 7,
        save_to_case: save,
      },
      { headers: { 'Idempotency-Key': expect.any(String) } },
    )
  },
)

it.each([undefined, null, 0, '7'])(
  'blocks requests without valid application context: %s',
  async (caseId) => {
    await expect(pluginService.executePlugin('Example', { case_id: 999 }, caseId)).rejects.toThrow(
      'active case',
    )
    expect(api.post).not.toHaveBeenCalled()
  },
)
