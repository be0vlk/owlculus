import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { useHuntStore } from '@/stores/huntStore'
import { useActiveCaseStore } from '@/stores/activeCase'
import { huntService } from '@/services/hunt'
import { caseService } from '@/services/case'
import HuntsDashboard from '../HuntsDashboard.vue'
import HuntExecutionHistory from '@/components/hunts/HuntExecutionHistory.vue'

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
const mountDashboard = (stubs = {}) =>
  shallowMount(HuntsDashboard, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        BaseDashboard: { template: '<div><slot /></div>' },
        VCard: { template: '<div><slot /></div>' },
        VTabsWindow: { template: '<div><slot /></div>' },
        VTabsWindowItem: { template: '<div><slot /></div>' },
        ...stubs,
      },
    },
  })
beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
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

afterEach(() => {
  useHuntStore().resetCaseExecutions()
  vi.useRealTimers()
})

it.each(['running', 'completed'])(
  'projects newer %s live output into cards and history despite stale reads and duplicate hints',
  async (status) => {
    await useActiveCaseStore().initialize(1)
    const initial = {
      ...execution(10, 1),
      status: 'running',
      revision: 2,
      hunt: { display_name: 'Lookup', category: 'domain' },
      steps: [],
    }
    const summary = {
      id: 10,
      case_id: 1,
      status: 'running',
      created_at: '2026-01-01',
      hunt_display_name: 'Lookup',
      hunt_category: 'domain',
    }
    huntService.getCaseExecutions.mockResolvedValue([summary, summary])
    huntService.getExecution.mockResolvedValue(initial)
    let notify
    huntService.createExecutionStream.mockImplementation(async (_id, onMessage) => {
      notify = onMessage
      return {}
    })
    const wrapper = mountDashboard()
    await flushPromises()
    let finishOld
    huntService.getExecution.mockReturnValueOnce(
      new Promise((resolve) => {
        finishOld = resolve
      }),
    )
    const store = useHuntStore()
    const pending = store.getExecution(10, true)
    const latest = {
      ...initial,
      status,
      revision: 4,
      progress: 0.8,
      steps: [{ id: 1, output: { results: ['new'] } }],
    }
    huntService.getExecution.mockResolvedValue(latest)
    notify({ event_type: 'update', revision: 4, cursor: '4-0' })
    notify({ event_type: 'update', revision: 4, cursor: '4-0' })
    await flushPromises()
    finishOld({ ...initial, progress: 0.1 })
    await pending
    await store.getCaseExecutions(1)
    await flushPromises()
    const cards = wrapper.findAllComponents({ name: 'HuntProgressCard' })
    expect(cards).toHaveLength(1)
    expect(cards[0].props('execution')).toMatchObject(latest)
    if (status === 'completed') {
      expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([
        expect.objectContaining({
          ...latest,
          hunt_display_name: 'Lookup',
          hunt_category: 'domain',
        }),
      ])
    }
    wrapper.unmount()
  },
)

it('shows one history row when submission retries return an existing execution identity', async () => {
  await useActiveCaseStore().initialize(1)
  const wrapper = mountDashboard()
  await flushPromises()
  const result = {
    ...execution(10, 1),
    revision: 3,
    hunt: { display_name: 'Lookup', category: 'domain' },
  }
  huntService.executeHunt.mockResolvedValue(result)
  huntService.getExecution.mockResolvedValue(result)
  wrapper
    .findComponent({ name: 'HuntCatalog' })
    .vm.$emit('execute', { id: 7, display_name: 'Lookup' })
  await flushPromises()
  const modal = wrapper.findComponent({ name: 'HuntExecutionModal' })
  const submission = { huntId: 7, caseId: 1, parameters: { domain: 'example.org' } }
  modal.vm.$emit('execute', submission)
  await flushPromises()
  modal.vm.$emit('execute', submission)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([
    expect.objectContaining({
      id: 10,
      status: 'completed',
      hunt_display_name: 'Lookup',
      hunt_category: 'domain',
    }),
  ])
  wrapper.unmount()
})

it('refreshes changed terminal summaries durably and keeps retained history on failure and retry', async () => {
  await useActiveCaseStore().initialize(1)
  const store = useHuntStore()
  const detail = {
    ...execution(10, 1),
    revision: 4,
    progress: 1,
    hunt: { display_name: 'Domain Lookup', category: 'domain' },
    steps: [{ id: 1, output: { results: ['retained'] } }],
  }
  huntService.getExecution.mockResolvedValue(detail)
  await store.getExecution(10, true)
  const wrapper = mountDashboard()
  await flushPromises()
  huntService.getCaseExecutions.mockResolvedValue([{ ...execution(10, 1), status: 'partial' }])
  huntService.getExecution.mockRejectedValueOnce(new Error('Temporary outage'))
  await store.getCaseExecutions(1)
  await flushPromises()
  const history = () => wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')
  expect(history()).toEqual([expect.objectContaining(detail)])
  expect(wrapper.text()).toContain('Failed to fetch execution')
  huntService.getExecution.mockResolvedValue({ ...detail, revision: 5, status: 'partial' })
  await store.getCaseExecutions(1)
  await flushPromises()
  expect(history()).toEqual([
    expect.objectContaining({ ...detail, revision: 5, status: 'partial' }),
  ])
  expect(wrapper.text()).not.toContain('Failed to fetch execution')
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('ignores a delayed history detail after newer terminal observation', async () => {
  await useActiveCaseStore().initialize(1)
  const initial = { ...execution(10, 1), status: 'running', revision: 2, progress: 0.2 }
  huntService.getCaseExecutions.mockResolvedValue([{ ...execution(10, 1), status: 'running' }])
  huntService.getExecution.mockResolvedValue(initial)
  let notify
  huntService.createExecutionStream.mockImplementation(async (_id, callback) => {
    notify = callback
    return {}
  })
  const wrapper = mountDashboard()
  await flushPromises()
  let finish
  huntService.getExecution.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const refresh = useHuntStore().getCaseExecutions(1)
  await flushPromises()
  const latest = {
    ...initial,
    status: 'completed',
    revision: 6,
    progress: 1,
    steps: [{ id: 1, output: { results: ['final'] } }],
  }
  huntService.getExecution.mockResolvedValue(latest)
  notify({ event_type: 'update', revision: 6, cursor: '6-0' })
  await flushPromises()
  finish({ ...initial, revision: 3 })
  await refresh
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([
    expect.objectContaining(latest),
  ])
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  wrapper.unmount()
})

it.each([401, 403, 404])('removes cached history after an access failure (%s)', async (status) => {
  await useActiveCaseStore().initialize(1)
  const wrapper = mountDashboard()
  await flushPromises()
  huntService.getCaseExecutions.mockRejectedValueOnce({ response: { status } })
  await expect(useHuntStore().getCaseExecutions(1)).rejects.toMatchObject({ response: { status } })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')).toEqual([])
  wrapper.unmount()
})

it('retains ordered history during failed refreshes and ignores old-case detail failures', async () => {
  await useActiveCaseStore().initialize(1)
  huntService.getCaseExecutions.mockResolvedValueOnce([
    execution(10, 1),
    { ...execution(11, 1), created_at: '2026-02-01' },
    execution(10, 1),
  ])
  const wrapper = mountDashboard()
  await flushPromises()
  const history = () => wrapper.findComponent({ name: 'HuntExecutionHistory' }).props('executions')
  expect(history().map(({ id }) => id)).toEqual([11, 10])
  huntService.getCaseExecutions.mockRejectedValueOnce(new Error('offline'))
  await expect(useHuntStore().getCaseExecutions(1)).rejects.toThrow('offline')
  await flushPromises()
  expect(history().map(({ id }) => id)).toEqual([11, 10])
  let fail
  huntService.getCaseExecutions.mockResolvedValueOnce([{ ...execution(10, 1), status: 'partial' }])
  huntService.getExecution.mockReturnValueOnce(
    new Promise((_resolve, reject) => {
      fail = reject
    }),
  )
  const refresh = useHuntStore().getCaseExecutions(1)
  await flushPromises()
  useActiveCaseStore().resolve(2)
  await flushPromises()
  fail(new Error('old case failure'))
  await refresh
  await flushPromises()
  expect(history()).toEqual([execution(20, 2)])
  expect(wrapper.text()).not.toContain('Failed to fetch execution')
  wrapper.unmount()
})

it('keeps searchable names, category filters, targets and terminal membership through detail enrichment', async () => {
  await useActiveCaseStore().initialize(1)
  huntService.getCaseExecutions.mockResolvedValue([
    {
      ...execution(10, 1),
      hunt_display_name: 'Domain Lookup',
      hunt_category: 'domain',
      initial_parameters: { domain: 'example.org' },
      progress: 1,
    },
    {
      ...execution(11, 1),
      status: 'partial',
      created_at: '2026-02-01',
      hunt_display_name: 'Person Lookup',
      hunt_category: 'person',
      initial_parameters: { email: 'person@example.org' },
      progress: 0.5,
    },
    {
      ...execution(12, 1),
      status: 'pending',
      hunt_display_name: 'Queued Lookup',
      hunt_category: 'domain',
    },
  ])
  huntService.getExecution.mockResolvedValue({
    ...execution(12, 1),
    status: 'pending',
    revision: 1,
  })
  const wrapper = mountDashboard({
    HuntExecutionHistory,
    VTextField: { name: 'VTextField', props: ['modelValue'], template: '<input />' },
    VSelect: { name: 'VSelect', props: ['modelValue', 'items'], template: '<select />' },
  })
  await flushPromises()
  const history = wrapper.findComponent(HuntExecutionHistory)
  const rows = () => history.findComponent({ name: 'VDataTable' }).props('items')
  expect(rows().map((row) => row.hunt_display_name)).toEqual(['Person Lookup', 'Domain Lookup'])
  expect(rows().find((row) => row.id === 10).target).toBe('example.org')
  huntService.getExecution.mockResolvedValueOnce({
    ...execution(10, 1),
    revision: 3,
    hunt: { id: 7, display_name: 'Domain Lookup', category: 'domain' },
    steps: null,
  })
  await useHuntStore().getExecution(10, true)
  await useHuntStore().getCaseExecutions(1)
  await flushPromises()
  const selects = history.findAllComponents({ name: 'VSelect' })
  expect(selects[1].props('items')).toContainEqual({ title: 'Domain', value: 'domain' })
  selects[1].vm.$emit('update:modelValue', 'domain')
  await flushPromises()
  expect(rows().map((row) => row.id)).toEqual([10])
  history.findComponent({ name: 'VTextField' }).vm.$emit('update:modelValue', 'example.org')
  await flushPromises()
  expect(rows().map((row) => row.id)).toEqual([10])
  selects[0].vm.$emit('update:modelValue', 'failed')
  await flushPromises()
  expect(history.text()).toContain('No executions found')
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  wrapper.unmount()
})
