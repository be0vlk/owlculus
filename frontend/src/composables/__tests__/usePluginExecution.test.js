import { afterEach, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { pluginService } from '@/services/plugin'
import { usePluginExecution } from '../usePluginExecution'

vi.mock('@/services/plugin', () => ({
  pluginService: { getExecution: vi.fn(), getResults: vi.fn() },
}))
afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

it('reopens ordered typed results and stops polling at completion', async () => {
  vi.useFakeTimers()
  pluginService.getExecution
    .mockResolvedValueOnce({ status: 'queued' })
    .mockResolvedValue({ status: 'completed' })
  pluginService.getResults.mockResolvedValueOnce({ items: [], cursor: 0 }).mockResolvedValue({
    items: [
      { type: 'data', data: { domain: 'example.org' } },
      { type: 'complete', data: {} },
    ],
    cursor: 4,
  })
  const scope = effectScope()
  const view = scope.run(() => usePluginExecution())
  view.observe(12)
  await flushPromises()
  expect(view.execution.value.status).toBe('queued')
  await vi.advanceTimersByTimeAsync(1000)
  expect(view.results.value[0].data.domain).toBe('example.org')
  expect(view.execution.value.status).toBe('completed')
  await vi.advanceTimersByTimeAsync(30000)
  expect(pluginService.getExecution).toHaveBeenCalledTimes(2)
  scope.stop()
})

it('navigation aborts observation without cancelling or submitting work', async () => {
  vi.useFakeTimers()
  pluginService.getExecution.mockResolvedValue({ status: 'running' })
  pluginService.getResults.mockResolvedValue({ items: [], cursor: 0 })
  const scope = effectScope()
  scope.run(() => usePluginExecution()).observe(12)
  await flushPromises()
  const signal = pluginService.getExecution.mock.calls[0][1]
  scope.stop()
  expect(signal.aborted).toBe(true)
  await vi.advanceTimersByTimeAsync(30000)
  expect(pluginService.getExecution).toHaveBeenCalledTimes(1)
})
