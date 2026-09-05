import { afterEach, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { pluginService } from '@/services/plugin'
import { usePluginExecution } from '../usePluginExecution'

vi.mock('@/services/plugin', () => ({
  pluginService: { getExecution: vi.fn(), getResults: vi.fn(), cancelExecution: vi.fn() },
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

it('keeps partial output and polls while cancellation cleanup is pending', async () => {
  vi.useFakeTimers()
  pluginService.getExecution.mockResolvedValue({ id: 12, status: 'running', revision: 2 })
  pluginService.getResults.mockResolvedValue({
    items: [{ type: 'data', data: 'retained' }],
    cursor: 2,
  })
  pluginService.cancelExecution.mockResolvedValue({ id: 12, status: 'cancelling', revision: 3 })
  const scope = effectScope()
  const view = scope.run(() => usePluginExecution())
  view.observe(12)
  await flushPromises()
  await view.cancel()
  expect(view.execution.value.status).toBe('cancelling')
  expect(view.results.value).toHaveLength(1)
  pluginService.getResults.mockResolvedValue({ items: [], cursor: 2 })
  await vi.advanceTimersByTimeAsync(1000)
  expect(view.execution.value.status).toBe('cancelling')
  pluginService.getExecution.mockResolvedValue({ id: 12, status: 'cancelled', revision: 4 })
  await vi.advanceTimersByTimeAsync(1500)
  const calls = pluginService.getExecution.mock.calls.length
  await vi.advanceTimersByTimeAsync(30000)
  expect(pluginService.getExecution).toHaveBeenCalledTimes(calls)
  expect(view.results.value).toHaveLength(1)
  scope.stop()
})

it('ignores a delayed cancellation response after a newer terminal poll', async () => {
  vi.useFakeTimers()
  pluginService.getExecution
    .mockResolvedValueOnce({ id: 12, status: 'running', revision: 2 })
    .mockResolvedValue({ id: 12, status: 'cancelled', revision: 4 })
  pluginService.getResults.mockResolvedValue({ items: [], cursor: 0 })
  let resolveCancel
  pluginService.cancelExecution.mockReturnValue(
    new Promise((resolve) => {
      resolveCancel = resolve
    }),
  )
  const scope = effectScope()
  const view = scope.run(() => usePluginExecution())
  view.observe(12)
  await flushPromises()
  const pending = view.cancel()
  await vi.advanceTimersByTimeAsync(1000)
  resolveCancel({ id: 12, status: 'cancelling', revision: 3 })
  await pending
  expect(view.execution.value.status).toBe('cancelled')
  await vi.advanceTimersByTimeAsync(30000)
  expect(pluginService.getExecution).toHaveBeenCalledTimes(2)
  scope.stop()
})
