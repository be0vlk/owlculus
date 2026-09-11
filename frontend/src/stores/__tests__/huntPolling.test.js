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
    .mockResolvedValue({ id: 1, status: 'cancelled', revision: 4, steps: [] })
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

it('refreshes hunt step output on a live hint and releases the subscription on navigation', async () => {
  let notify
  const socket = {}
  huntService.createExecutionStream.mockImplementation(async (_id, message) => {
    notify = message
    return socket
  })
  huntService.closeExecutionStream = vi.fn()
  huntService.getExecution.mockResolvedValue({ id: 1, status: 'running', revision: 2, steps: [] })
  const store = useHuntStore()
  store.subscribeToExecution(1)
  await flushPromises()
  huntService.getExecution.mockResolvedValue({
    id: 1,
    status: 'running',
    revision: 3,
    steps: [{ output: { results: ['found'] } }],
  })
  notify({ event_type: 'update', revision: 3, cursor: '3-0' })
  await flushPromises()
  expect(store.activeExecutions[1].steps[0].output.results).toEqual(['found'])
  store.unsubscribeFromExecution(1)
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(socket)
  const reads = huntService.getExecution.mock.calls.length
  notify({ event_type: 'update', revision: 4, cursor: '4-0' })
  await vi.advanceTimersByTimeAsync(60000)
  expect(huntService.getExecution).toHaveBeenCalledTimes(reads)
  expect(huntService.executeHunt).not.toHaveBeenCalled()
})

it('releases workflow reads and ignores old cleanup on a later visit to the same execution', async () => {
  let finish
  huntService.getExecution.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const store = useHuntStore()
  const old = store.openWorkflow({ caseId: 1, executionId: 7 })
  const pending = old.refresh()
  const signal = huntService.getExecution.mock.calls.at(-1)[2]
  const current = store.openWorkflow({ caseId: 1, executionId: 7 })
  expect(signal.aborted).toBe(true)
  huntService.getExecution.mockResolvedValue({
    id: 7,
    case_id: 1,
    status: 'completed',
    revision: 4,
    steps: [],
  })
  await current.refresh()
  old.release()
  finish({ id: 7, case_id: 1, status: 'running', revision: 2 })
  await pending
  expect(store.activeExecutions[7].status).toBe('completed')
  expect(current.isCurrent()).toBe(true)
  current.release()
  expect(vi.getTimerCount()).toBe(0)
})
