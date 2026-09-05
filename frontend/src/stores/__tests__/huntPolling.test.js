import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { huntService } from '@/services/hunt'
import { useHuntStore } from '../huntStore'

vi.mock('@/services/hunt', () => ({
  huntService: {
    getExecution: vi.fn(),
    executeHunt: vi.fn(),
    createExecutionStream: vi.fn(),
    cancelExecution: vi.fn(),
  },
}))
beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers()
  vi.clearAllMocks()
})
afterEach(() => {
  useHuntStore().resetCaseExecutions()
  vi.useRealTimers()
})
it('observes queued, running and partial results without resubmitting and stops at terminal state', async () => {
  huntService.getExecution
    .mockResolvedValueOnce({ id: 1, status: 'pending' })
    .mockResolvedValueOnce({ id: 1, status: 'running' })
    .mockResolvedValueOnce({ id: 1, status: 'partial', steps: [{ output: { result_count: 1 } }] })
  const store = useHuntStore()
  store.subscribeToExecution(1)
  await flushPromises()
  expect(store.activeExecutions[1].status).toBe('pending')
  await vi.advanceTimersByTimeAsync(1000)
  expect(store.activeExecutions[1].status).toBe('running')
  await vi.advanceTimersByTimeAsync(1500)
  expect(store.activeExecutions[1].steps[0].output.result_count).toBe(1)
  await vi.advanceTimersByTimeAsync(30000)
  expect(huntService.getExecution).toHaveBeenCalledTimes(3)
  expect(huntService.executeHunt).not.toHaveBeenCalled()
})
it('discards an in-flight observation after navigation', async () => {
  let finish
  huntService.getExecution.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const store = useHuntStore()
  store.subscribeToExecution(1)
  store.unsubscribeFromExecution(1)
  finish({ id: 1, status: 'running' })
  await flushPromises()
  await vi.advanceTimersByTimeAsync(30000)
  expect(store.activeExecutions).toEqual({})
  expect(huntService.getExecution).toHaveBeenCalledTimes(1)
})

it('retains terminal state when an older cancellation response arrives late', async () => {
  huntService.getExecution
    .mockResolvedValueOnce({ id: 1, status: 'running', revision: 2 })
    .mockResolvedValue({ id: 1, status: 'cancelled', revision: 4 })
  let resolveCancel
  huntService.cancelExecution.mockReturnValue(
    new Promise((resolve) => {
      resolveCancel = resolve
    }),
  )
  const store = useHuntStore()
  store.subscribeToExecution(1)
  await flushPromises()
  const pending = store.cancelExecution(1)
  await vi.advanceTimersByTimeAsync(1000)
  resolveCancel({ execution_id: 1, status: 'cancelling', revision: 3 })
  await pending
  expect(store.activeExecutions[1].status).toBe('cancelled')
  await vi.advanceTimersByTimeAsync(30000)
  expect(huntService.getExecution).toHaveBeenCalledTimes(2)
})
