import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { useActiveCaseStore } from '@/stores/activeCase'
import { huntService } from '@/services/hunt'
import { caseService } from '@/services/case'
import HuntsDashboard from '../HuntsDashboard.vue'

vi.mock('@/services/hunt', () => ({
  huntService: {
    getHunts: vi.fn(),
    getCaseExecutions: vi.fn(),
    getExecution: vi.fn(),
    executeHunt: vi.fn(),
    createExecutionStream: vi.fn(),
    closeExecutionStream: vi.fn(),
  },
}))
vi.mock('@/services/case', () => ({ caseService: { getCases: vi.fn() } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/composables/useNotifications', () => ({
  useNotifications: () => ({ showNotification: vi.fn() }),
}))
const cases = [{ id: 1 }, { id: 2 }]
const execution = (id, case_id) => ({ id, case_id, status: 'completed', created_at: '2026-01-01' })
const mountDashboard = () =>
  shallowMount(HuntsDashboard, {
    global: {
      stubs: {
        BaseDashboard: { template: '<div><slot /></div>' },
        VCard: { template: '<div><slot /></div>' },
        VTabsWindow: { template: '<div><slot /></div>' },
        VTabsWindowItem: { template: '<div><slot /></div>' },
      },
    },
  })
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  caseService.getCases.mockResolvedValue(cases)
  huntService.getHunts.mockResolvedValue([{ id: 7, display_name: 'Lookup' }])
  huntService.getCaseExecutions.mockImplementation(async (id) => [execution(id * 10, id)])
  huntService.createExecutionStream.mockResolvedValue({})
})
it('loads only the active case and discards a late response from the previous case', async () => {
  const context = useActiveCaseStore()
  await context.initialize(1)
  let finishOld
  huntService.getCaseExecutions.mockReturnValueOnce(
    new Promise((resolve) => {
      finishOld = resolve
    }),
  )
  const wrapper = mountDashboard()
  await flushPromises()
  expect(huntService.getCaseExecutions).toHaveBeenCalledExactlyOnceWith(1)
  context.resolve(2)
  await flushPromises()
  finishOld([execution(10, 1)])
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([
    execution(20, 2),
  ])
  wrapper.unmount()
})
it('blocks hunt actions without context and submits with the active case', async () => {
  const wrapper = mountDashboard()
  await flushPromises()
  expect(huntService.getCaseExecutions).not.toHaveBeenCalled()
  expect(wrapper.findComponent({ name: 'HuntCatalog' }).exists()).toBe(false)
  await useActiveCaseStore().initialize(2)
  await flushPromises()
  wrapper
    .findComponent({ name: 'HuntCatalog' })
    .vm.$emit('execute', { id: 7, display_name: 'Lookup' })
  await flushPromises()
  const modal = wrapper.findComponent({ name: 'HuntExecutionModal' })
  expect(modal.props('caseId')).toBe(2)
  huntService.executeHunt.mockResolvedValue(execution(30, 2))
  huntService.getExecution.mockResolvedValue(execution(30, 2))
  modal.vm.$emit('execute', { huntId: 7, caseId: 1, parameters: { domain: 'example.org' } })
  await flushPromises()
  expect(huntService.executeHunt).toHaveBeenCalledWith(7, 2, { domain: 'example.org' })
  wrapper.unmount()
})

it('discards a polling response after switching cases', async () => {
  await useActiveCaseStore().initialize(1)
  const running = { ...execution(10, 1), status: 'running' }
  huntService.getCaseExecutions.mockResolvedValueOnce([running])
  huntService.getExecution.mockResolvedValueOnce(running)
  let finishPoll
  huntService.getExecution.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishPoll = resolve
      }),
  )
  const wrapper = mountDashboard()
  await flushPromises()
  useActiveCaseStore().resolve(2)
  await flushPromises()
  finishPoll(running)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([
    execution(20, 2),
  ])
  wrapper.unmount()
})
