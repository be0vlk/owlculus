import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createAppRouter, routes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useHuntStore } from '@/stores/huntStore'
import { caseService } from '@/services/case'
import { huntService } from '@/services/hunt'
import HuntsDashboard from '../HuntsDashboard.vue'
import HuntExecution from '../HuntExecution.vue'

vi.mock('@/services/case', () => ({ caseService: { getCases: vi.fn() } }))
vi.mock('@/services/hunt', () => ({
  huntService: {
    getHunts: vi.fn(),
    getCaseExecutions: vi.fn(),
    getExecution: vi.fn(),
    createExecutionStream: vi.fn(),
    closeExecutionStream: vi.fn(),
    executeHunt: vi.fn(),
    cancelExecution: vi.fn(),
  },
}))
vi.mock('@/composables/useNotifications', () => ({
  useNotifications: () => ({ showNotification: vi.fn() }),
}))

const detail = (id = 7, caseId = 1, status = 'running', extra = {}) => ({
  id,
  case_id: caseId,
  status,
  revision: 2,
  steps: [],
  hunt: { display_name: `Hunt ${id}`, category: 'person' },
  started_at: '2026-09-06T00:00:00Z',
  ...extra,
})
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
let wrapper, router, pinia
const streams = []
beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
  localStorage.clear()
  sessionStorage.clear()
  streams.length = 0
  pinia = createPinia()
  setActivePinia(pinia)
  Object.assign(useAuthStore(), {
    isInitialized: true,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin' },
  })
  caseService.getCases.mockResolvedValue([{ id: 1 }, { id: 2 }])
  huntService.getHunts.mockResolvedValue([])
  huntService.getCaseExecutions.mockImplementation(async (id) => [detail(id === 1 ? 7 : 8, id)])
  huntService.getExecution.mockImplementation(async (id) =>
    detail(Number(id), Number(id) === 8 ? 2 : 1),
  )
  huntService.createExecutionStream.mockImplementation(async (id, notify, interrupt, cursor) => {
    const stream = { id, notify, interrupt, cursor }
    streams.push(stream)
    return stream
  })
  router = createAppRouter(
    createMemoryHistory(),
    routes.map((route) => ({
      ...route,
      component: ['Hunts', 'LegacyHunts'].includes(route.name)
        ? HuntsDashboard
        : ['HuntExecution', 'LegacyHuntExecution'].includes(route.name)
          ? HuntExecution
          : route.component
            ? { template: '<div>Other page</div>' }
            : undefined,
    })),
  )
})
afterEach(() => {
  wrapper?.unmount()
  useHuntStore().resetCaseExecutions()
  vi.useRealTimers()
})
async function open(path) {
  await router.push(path)
  wrapper = shallowMount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [pinia, router],
        renderStubDefaultSlot: true,
        stubs: {
          RouterView: false,
          HuntsDashboard: false,
          HuntExecution: false,
          BaseDashboard: { template: '<div><slot name="header-actions" /><slot /></div>' },
          HuntCatalog: true,
          HuntProgressCard: true,
          HuntExecutionModal: true,
          HuntDetailsModal: true,
          HuntExecutionHistory: true,
          HuntResultsSummary: true,
          HuntStepResults: true,
          ExecutionWaiting: true,
        },
      },
    },
  )
  await flushPromises()
}

it('owns dashboard/detail navigation, late reads, stream openings and old notifications', async () => {
  await open('/case/1/hunts')
  const store = useHuntStore()
  const oldStream = streams[0]
  const oldRead = deferred()
  huntService.getExecution.mockReturnValueOnce(oldRead.promise)
  oldStream.notify({ cursor: '3-0' })
  const oldSignal = huntService.getExecution.mock.calls.at(-1)[2]
  const opening = deferred()
  huntService.createExecutionStream.mockReturnValueOnce(opening.promise)
  await router.push('/case/1/hunts/execution/7')
  await flushPromises()
  expect(oldSignal.aborted).toBe(true)
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(oldStream)
  expect(wrapper.text()).toContain('Hunt 7')
  oldRead.reject(new Error('Old workflow failed'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('Old workflow failed')
  await router.push('/case/1/hunts')
  await flushPromises()
  const lateStream = { id: 'late' }
  opening.resolve(lateStream)
  await flushPromises()
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(lateStream)
  const reads = huntService.getExecution.mock.calls.length
  oldStream.notify({ cursor: '9-0' })
  await flushPromises()
  expect(huntService.getExecution).toHaveBeenCalledTimes(reads)
  expect(store.runningExecutions.map((item) => item.id)).toEqual([7])
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  expect(huntService.cancelExecution).not.toHaveBeenCalled()
  wrapper.unmount()
  const readsAtRelease = huntService.getExecution.mock.calls.length
  await vi.advanceTimersByTimeAsync(60000)
  expect(huntService.getExecution).toHaveBeenCalledTimes(readsAtRelease)
  expect(vi.getTimerCount()).toBe(0)
})

it('replaces the selected execution and Case during a pending detail read', async () => {
  await open('/case/1/hunts/execution/7')
  const pending = deferred()
  huntService.getExecution.mockReturnValueOnce(pending.promise)
  const refresh = wrapper.findComponent(HuntExecution).vm.refreshExecution()
  const signal = huntService.getExecution.mock.calls.at(-1)[2]
  await router.push('/case/2/hunts/execution/8')
  await flushPromises()
  expect(signal.aborted).toBe(true)
  expect(useActiveCaseStore().activeCaseId).toBe(2)
  expect(wrapper.text()).toContain('Hunt 8')
  expect(wrapper.text()).not.toContain('Hunt 7')
  pending.resolve(detail(7, 1, 'completed', { revision: 9 }))
  await refresh
  expect(Object.keys(useHuntStore().activeExecutions)).toEqual(['8'])
  expect(wrapper.text()).toContain('Hunt 8')
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  expect(huntService.cancelExecution).not.toHaveBeenCalled()
})

it.each(['/hunts/execution/7', '/case/2/hunts/execution/7'])(
  'reconciles authorized ownership before rendering a direct link: %s',
  async (path) => {
    await open('/case/2/hunts')
    const ownership = deferred()
    huntService.getExecution.mockReturnValueOnce(ownership.promise)
    const navigation = router.push(path)
    await flushPromises()
    expect(useHuntStore().activeExecutions[7]).toBeUndefined()
    expect(wrapper.findComponent(HuntExecution).exists()).toBe(false)
    ownership.resolve(detail())
    await navigation
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/case/1/hunts/execution/7')
    expect(useActiveCaseStore().activeCaseId).toBe(1)
    expect(wrapper.text()).toContain('Hunt 7')
    expect(Object.keys(useHuntStore().activeExecutions)).toEqual(['7'])
  },
)

it.each([401, 403, 404])(
  'removes retained results and actions when observation loses access (%s)',
  async (status) => {
    await open('/case/1/hunts/execution/7')
    huntService.getExecution.mockRejectedValue({
      response: { status, data: { detail: 'No access' } },
    })
    streams[0].notify({ cursor: '3-0' })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Hunt 7')
    expect(wrapper.text()).toContain('No access')
    expect(useHuntStore().activeExecutions).toEqual({})
    const readsAtRelease = huntService.getExecution.mock.calls.length
    await vi.advanceTimersByTimeAsync(60000)
    expect(huntService.getExecution).toHaveBeenCalledTimes(readsAtRelease)
    expect(vi.getTimerCount()).toBe(0)
    await router.push('/hunts/execution/7')
    expect(router.currentRoute.value.path).toBe('/cases')
  },
)

it('redirects direct links when no Cases are accessible', async () => {
  caseService.getCases.mockResolvedValue([])
  await open('/hunts/execution/7')
  expect(router.currentRoute.value.path).toBe('/cases')
  expect(wrapper.findComponent(HuntExecution).exists()).toBe(false)
  expect(huntService.getExecution).not.toHaveBeenCalled()
})

it('recovers reads and reconnect bursts, retaining output until complete terminal details stop observation', async () => {
  await open('/case/1/hunts/execution/7')
  const view = wrapper.findComponent(HuntExecution)
  const store = useHuntStore()
  huntService.getExecution.mockRejectedValueOnce(new Error('Temporary read failure'))
  await view.vm.refreshExecution()
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('Temporary read failure')
  expect(wrapper.text()).toContain('Hunt 7')
  const first = streams[0]
  first.interrupt()
  expect(store.error).toContain('interrupted')
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(wrapper.text()).not.toContain('Temporary read failure')
  expect(wrapper.text()).not.toContain('interrupted')
  expect(streams).toHaveLength(2)
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(first)
  const reading = deferred()
  huntService.getExecution.mockReturnValueOnce(reading.promise)
  const reads = huntService.getExecution.mock.calls.length
  streams[1].notify({ cursor: '5-0', event_type: 'resync' })
  for (let n = 0; n < 20; n++) streams[1].notify({ cursor: '5-0', event_type: 'resync' })
  expect(huntService.getExecution).toHaveBeenCalledTimes(reads + 1)
  reading.resolve(detail(7, 1, 'completed', { revision: 5, steps: undefined }))
  huntService.getExecution.mockResolvedValue(detail(7, 1, 'completed', { revision: 5, steps: [] }))
  await flushPromises()
  expect(store.activeExecutions[7].status).toBe('completed')
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  expect(store.activeExecutions[7].steps).toEqual([])
  const terminalReads = huntService.getExecution.mock.calls.length
  await vi.advanceTimersByTimeAsync(60000)
  expect(huntService.getExecution).toHaveBeenCalledTimes(terminalReads)
  expect(vi.getTimerCount()).toBe(0)
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(streams[1])
  await view.vm.refreshExecution()
  expect(huntService.getExecution).toHaveBeenCalledTimes(terminalReads + 1)
  await router.push('/cases')
  await router.push('/case/1/hunts/execution/7')
  await flushPromises()
  expect(wrapper.text()).toContain('Hunt 7')
  expect(streams).toHaveLength(2)
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  expect(huntService.cancelExecution).not.toHaveBeenCalled()
})

it('bounds retries during an outage and keeps action errors through unrelated successful reads', async () => {
  await open('/case/1/hunts/execution/7')
  huntService.getExecution.mockRejectedValue(new Error('offline'))
  await vi.advanceTimersByTimeAsync(60000)
  expect(huntService.getExecution.mock.calls.length).toBeLessThan(16)
  expect(wrapper.text()).toContain('Hunt 7')
  expect(wrapper.text()).toContain('retrying')
  huntService.cancelExecution.mockRejectedValue(new Error('Cancellation unavailable'))
  await wrapper.findComponent(HuntExecution).vm.handleCancelExecution()
  huntService.getExecution.mockResolvedValue(detail())
  streams[0].notify({ cursor: '3-0' })
  await flushPromises()
  expect(useHuntStore().error).toBe('Failed to cancel execution')
  expect(wrapper.text()).toContain('Failed to cancel execution')
  expect(huntService.executeHunt).not.toHaveBeenCalled()
})

it('replaces an execution within the same Case without accepting a late failure or leaking its timer', async () => {
  await open('/case/1/hunts/execution/7')
  const pending = deferred()
  huntService.getExecution.mockReturnValueOnce(pending.promise)
  const refresh = wrapper.findComponent(HuntExecution).vm.refreshExecution()
  huntService.getExecution.mockImplementation(async (id) => detail(Number(id), 1, 'pending'))
  await router.push('/case/1/hunts/execution/9')
  await flushPromises()
  expect(wrapper.text()).toContain('Hunt 9')
  expect(wrapper.text()).not.toContain('Hunt 7')
  pending.reject(new Error('Old selection failed'))
  await refresh
  await flushPromises()
  expect(wrapper.text()).not.toContain('Old selection failed')
  expect(huntService.closeExecutionStream).toHaveBeenCalledWith(streams[0])
  wrapper.unmount()
  await vi.advanceTimersByTimeAsync(60000)
  expect(vi.getTimerCount()).toBe(0)
})
