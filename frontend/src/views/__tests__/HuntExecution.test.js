import { defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useHuntStore } from '@/stores/huntStore'
import { huntService } from '@/services/hunt'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HuntExecution from '../HuntExecution.vue'

const mocks = vi.hoisted(() => ({
  execution: null,
  replace: vi.fn(),
  exportExecution: vi.fn(),
  downloadBlob: vi.fn(),
  showNotification: vi.fn(),
  getExecution: vi.fn(),
  cancelExecution: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7', caseId: '42' } }),
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace }),
}))

vi.mock('@/services/hunt', () => ({
  huntService: {
    exportExecution: mocks.exportExecution,
    executeHunt: vi.fn(),
    getExecution: mocks.getExecution,
    cancelExecution: mocks.cancelExecution,
    getCaseExecutions: vi.fn(),
    createExecutionStream: vi.fn(),
    closeExecutionStream: vi.fn(),
  },
}))

vi.mock('@/utils/download', () => ({ downloadBlob: mocks.downloadBlob }))

vi.mock('@/composables/useNotifications', () => ({
  useNotifications: () => ({ showNotification: mocks.showNotification }),
}))

const BaseDashboardStub = defineComponent({
  template: '<div><slot name="header-actions" /><slot /></div>',
})
const MenuStub = defineComponent({
  template: '<div data-testid="export-menu"><slot name="activator" :props="{}" /><slot /></div>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  template: '<button :disabled="disabled"><slot /></button>',
})
const ListItemStub = defineComponent({
  props: { title: String, disabled: Boolean },
  emits: ['click'],
  template:
    '<button :data-testid="`export-${title.split(\' \').at(-1).toLowerCase()}`" :disabled="disabled" @click="$emit(\'click\')">{{ title }}</button>',
})

const mountExecution = async (status, caseId = 42, detail = {}) => {
  mocks.execution = {
    id: 7,
    case_id: caseId,
    status,
    progress: 1,
    initial_parameters: {},
    context_data: null,
    created_at: '2026-09-01T00:00:00Z',
    created_by_id: 1,
    hunt: { display_name: 'Person Hunt', category: 'person' },
    steps: [],
    ...detail,
  }
  mocks.getExecution.mockResolvedValue(mocks.execution)
  const wrapper = shallowMount(HuntExecution, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        BaseDashboard: BaseDashboardStub,
        VMenu: MenuStub,
        VBtn: ButtonStub,
        VList: defineComponent({ template: '<div><slot /></div>' }),
        VListItem: ListItemStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
  setActivePinia(createPinia())
})

afterEach(() => {
  useHuntStore().resetCaseExecutions()
  vi.useRealTimers()
})

describe('HuntExecution exports', () => {
  it.each(['completed', 'partial', 'failed', 'cancelled'])(
    'shows the export menu for a %s execution',
    async (status) => {
      const wrapper = await mountExecution(status)

      expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(true)
    },
  )

  it.each(['pending', 'running', 'cancelling'])(
    'hides the export menu for a %s execution',
    async (status) => {
      const wrapper = await mountExecution(status)

      expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(false)
    },
  )

  it.each(['pdf', 'json'])('downloads a backend-generated %s export', async (format) => {
    const artifact = {
      blob: new Blob(['export']),
      headers: { 'content-disposition': `attachment; filename="execution.${format}"` },
    }
    mocks.exportExecution.mockResolvedValue(artifact)
    const wrapper = await mountExecution('failed')

    await wrapper.get(`[data-testid="export-${format}"]`).trigger('click')
    await flushPromises()

    expect(mocks.exportExecution).toHaveBeenCalledWith(7, format)
    expect(mocks.downloadBlob).toHaveBeenCalledWith(artifact, `hunt-execution-7.${format}`)
    expect(mocks.showNotification).toHaveBeenCalledWith('Results exported successfully', 'success')
  })
})

it('reconciles an unexpected owner before rendering execution actions', async () => {
  const wrapper = await mountExecution('completed', 99)
  expect(mocks.replace).toHaveBeenCalledWith('/case/99/hunts/execution/7')
  expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(false)
})

it('does not reload an execution after cancellation completes on an unmounted page', async () => {
  let finishCancel
  mocks.cancelExecution.mockReturnValueOnce(
    new Promise((resolve) => {
      finishCancel = resolve
    }),
  )
  const wrapper = await mountExecution('running')
  const cancel = wrapper.findAll('button').find((button) => button.text().includes('Cancel'))
  await cancel.trigger('click')
  wrapper.unmount()
  finishCancel()
  await flushPromises()
  expect(mocks.getExecution).toHaveBeenCalledTimes(2)
})

const deferred = () => {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}

it.each(['running', 'completed'])(
  'keeps newer %s live results after an older manual refresh',
  async (status) => {
    let notify
    huntService.createExecutionStream.mockImplementation(async (_id, onMessage) => {
      notify = onMessage
      return {}
    })
    const wrapper = await mountExecution('running')
    const older = deferred()
    mocks.getExecution.mockReturnValueOnce(older.promise)
    const refresh = wrapper.findAll('button').find((button) => button.text().includes('Refresh'))
    await refresh.trigger('click')
    const latest = {
      ...mocks.execution,
      revision: 4,
      status,
      progress: 0.8,
      steps: [{ step_id: 'lookup', status: 'completed', output: { results: ['new'] } }],
    }
    mocks.getExecution.mockResolvedValue(latest)
    notify({ event_type: 'update', revision: 4, cursor: '4-0' })
    await flushPromises()
    older.resolve({ ...mocks.execution, revision: 2, progress: 0.1 })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(
      latest.steps[0],
    )
    expect(wrapper.text()).toContain(status === 'completed' ? 'Completed' : 'Running')
    wrapper.unmount()
  },
)

it('enriches equal revisions, preserves omitted steps, and accepts only newer authoritative empty steps', async () => {
  const wrapper = await mountExecution('completed')
  const store = useHuntStore()
  const read = async (snapshot, includeSteps = true) => {
    mocks.getExecution.mockResolvedValueOnce(snapshot)
    await store.getExecution(7, includeSteps)
    await flushPromises()
  }
  const detail = { ...mocks.execution, revision: 5, steps: null }
  await read(detail, false)
  const step = { id: 1, step_id: 'lookup', status: 'completed', output: { results: ['retained'] } }
  await read({ ...detail, steps: [step] })
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  await read({ ...detail, revision: 6 }, false)
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  await read({ ...detail, revision: 4 })
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  await read({ ...detail, revision: 7 })
  expect(wrapper.text()).toContain('No steps available')
  wrapper.unmount()
})

it('keeps the newer of two manual reads and retains output through cancellation acknowledgements', async () => {
  const wrapper = await mountExecution('completed')
  const store = useHuntStore()
  const older = deferred()
  const newer = deferred()
  mocks.getExecution.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
  const first = store.getExecution(7, true)
  const second = store.getExecution(7, true)
  const latest = {
    ...mocks.execution,
    revision: 8,
    steps: [{ id: 1, step_id: 'lookup', status: 'completed', output: { results: ['latest'] } }],
  }
  newer.resolve(latest)
  await second
  older.resolve({ ...mocks.execution, revision: 3, status: 'running' })
  await first
  mocks.cancelExecution.mockResolvedValue({
    execution_id: 7,
    status: 'cancelling',
    revision: 6,
    message: 'requested',
  })
  await store.cancelExecution(7)
  await flushPromises()
  expect(wrapper.text()).toContain('Completed')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(latest.steps[0])
  mocks.cancelExecution.mockResolvedValue({
    execution_id: 7,
    status: 'cancelled',
    revision: 9,
    message: 'cancelled',
  })
  await store.cancelExecution(7)
  await flushPromises()
  expect(wrapper.text()).toContain('Cancelled')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(latest.steps[0])
  wrapper.unmount()
})

it('retains detailed terminal output when same-Case history is loaded after a direct execution link', async () => {
  const wrapper = await mountExecution('completed')
  const store = useHuntStore()
  const latest = {
    ...mocks.execution,
    revision: 8,
    steps: [{ id: 1, status: 'completed', output: { results: ['retained'] } }],
  }
  mocks.getExecution.mockResolvedValueOnce(latest)
  await store.getExecution(7, true)
  huntService.getCaseExecutions.mockResolvedValue([
    {
      id: 7,
      case_id: 42,
      status: 'pending',
      hunt_display_name: 'Person Hunt',
      hunt_category: 'person',
    },
  ])
  await store.getCaseExecutions(42)
  await flushPromises()
  expect(wrapper.text()).toContain('Completed')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(latest.steps[0])
  wrapper.unmount()
})

it.each([null, [{ id: 1, status: 'completed', output: { results: ['updated'] } }]])(
  'recovers current revision steps after a non-step read (%j)',
  async (steps) => {
    const wrapper = await mountExecution('completed')
    const store = useHuntStore()
    const read = async (revision, resultSteps, includeSteps) => {
      mocks.getExecution.mockResolvedValueOnce({ ...mocks.execution, revision, steps: resultSteps })
      await store.getExecution(7, includeSteps)
      await flushPromises()
    }
    await read(5, [{ id: 1, status: 'completed', output: { results: ['old'] } }], true)
    await read(6, null, false)
    await read(6, steps, true)
    if (steps)
      expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(steps[0])
    else expect(wrapper.text()).toContain('No steps available')
    wrapper.unmount()
  },
)

it.each([undefined, 0])(
  'reopens legacy results with revision %s through repeated summaries',
  async (revision) => {
    let wrapper = await mountExecution('completed')
    const detail = {
      ...mocks.execution,
      revision,
      steps: [
        { id: 1, step_id: 'lookup', status: 'completed', output: { results: ['historical'] } },
      ],
    }
    mocks.getExecution.mockResolvedValue(detail)
    await useHuntStore().getExecution(7, true)
    huntService.getCaseExecutions.mockResolvedValue([
      {
        id: 7,
        case_id: 42,
        status: 'completed',
        progress: 1,
        hunt_display_name: 'Person Hunt',
        hunt_category: 'person',
      },
    ])
    await useHuntStore().getCaseExecutions(42)
    await useHuntStore().getCaseExecutions(42)
    await flushPromises()
    expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(
      detail.steps[0],
    )
    wrapper.unmount()
    await useHuntStore().getCaseExecutions(42)
    wrapper = await mountExecution('completed', 42, detail)
    expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(
      detail.steps[0],
    )
    expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(true)
    expect(huntService.executeHunt).not.toHaveBeenCalled()
    wrapper.unmount()
  },
)

it('retains results and accessible feedback on refresh failure and clears it on retry', async () => {
  const wrapper = await mountExecution('completed')
  mocks.getExecution.mockRejectedValueOnce(new Error('Temporary read failure'))
  const refresh = wrapper.findAll('button').find((button) => button.text().includes('Refresh'))
  await refresh.trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('Temporary read failure')
  expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(true)
  await wrapper
    .findAll('button')
    .find((button) => button.text().includes('Refresh'))
    .trigger('click')
  await flushPromises()
  expect(
    wrapper
      .findAll('[role="alert"]')
      .map((alert) => alert.text())
      .join(' '),
  ).not.toContain('Temporary read failure')
  wrapper.unmount()
})

it('reports export failure without discarding terminal results', async () => {
  const wrapper = await mountExecution('completed')
  mocks.exportExecution.mockRejectedValueOnce(new Error('offline'))
  await wrapper.get('[data-testid="export-json"]').trigger('click')
  await flushPromises()
  expect(mocks.showNotification).toHaveBeenCalledWith('Failed to export JSON', 'error')
  expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(true)
  wrapper.unmount()
})

it('shares pending cancellation with the module, prevents repeated requests and permits a failed action retry', async () => {
  const step = { id: 1, step_id: 'lookup', status: 'completed', output: { results: ['retained'] } }
  const wrapper = await mountExecution('running', 42, { revision: 2, steps: [step] })
  let fail
  mocks.cancelExecution.mockReturnValueOnce(
    new Promise((_resolve, reject) => {
      fail = reject
    }),
  )
  const cancel = () => wrapper.findAll('button').find((button) => button.text().includes('Cancel'))
  await cancel().trigger('click')
  // A second consumer of the Hunt seam must share the pending guard.
  const duplicate = useHuntStore().cancelExecution(7)
  expect(mocks.cancelExecution).toHaveBeenCalledTimes(1)
  expect(cancel().element.disabled).toBe(true)
  fail(new Error('Cancellation unavailable'))
  await duplicate
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('Cancellation unavailable')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  expect(cancel().element.disabled).toBe(false)
  mocks.cancelExecution.mockResolvedValue({ execution_id: 7, status: 'cancelling', revision: 3 })
  await cancel().trigger('click')
  await flushPromises()
  expect(mocks.cancelExecution).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('Cancelling')
  expect(wrapper.text()).not.toContain('Cancellation unavailable')
  expect(mocks.showNotification).toHaveBeenLastCalledWith('Cancellation requested', 'info')
  wrapper.unmount()
})

it('recovers equal-revision final output after terminal cancellation despite an older refresh and a transient failure', async () => {
  const step = { id: 1, step_id: 'lookup', status: 'completed', output: { results: ['retained'] } }
  const wrapper = await mountExecution('running', 42, { revision: 2, steps: [step] })
  const older = deferred()
  mocks.getExecution.mockReturnValueOnce(older.promise)
  const refresh = wrapper.findAll('button').find((button) => button.text().includes('Refresh'))
  await refresh.trigger('click')
  mocks.cancelExecution.mockResolvedValue({ execution_id: 7, status: 'cancelled', revision: 4 })
  await wrapper
    .findAll('button')
    .find((button) => button.text().includes('Cancel'))
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Cancelled')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  // The view must not make a competing detail request on acknowledgement.
  expect(mocks.getExecution).toHaveBeenCalledTimes(3)
  older.resolve({ ...mocks.execution, revision: 3 })
  await flushPromises()
  mocks.getExecution.mockRejectedValueOnce(new Error('offline'))
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('retrying')
  expect(wrapper.text()).toContain('Cancelled')
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(step)
  const finalStep = { ...step, output: { results: ['final'] } }
  mocks.getExecution.mockResolvedValue({
    ...mocks.execution,
    status: 'cancelled',
    revision: 4,
    steps: [finalStep],
  })
  await vi.advanceTimersByTimeAsync(1500)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(finalStep)
  expect(wrapper.text()).not.toContain('retrying')
  const reads = mocks.getExecution.mock.calls.length
  await vi.advanceTimersByTimeAsync(60000)
  expect(mocks.getExecution).toHaveBeenCalledTimes(reads)
  expect(huntService.executeHunt).not.toHaveBeenCalled()
  wrapper.unmount()
})

it.each(['completed', 'partial', 'failed', 'cancelled'])(
  'ignores a late cancellation acknowledgement after newer %s output without restarting reads or showing obsolete feedback',
  async (status) => {
    let notify
    huntService.createExecutionStream.mockImplementation(async (_id, callback) => {
      notify = callback
      return {}
    })
    const wrapper = await mountExecution('running', 42, { revision: 2 })
    const cancellation = deferred()
    mocks.cancelExecution.mockReturnValueOnce(cancellation.promise)
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Cancel'))
      .trigger('click')
    const finalStep = { id: 1, status: 'completed', output: { results: ['final'] } }
    mocks.getExecution.mockResolvedValue({
      ...mocks.execution,
      status,
      revision: 5,
      steps: [finalStep],
    })
    notify({ cursor: '5-0' })
    await flushPromises()
    const reads = mocks.getExecution.mock.calls.length
    cancellation.resolve({ execution_id: 7, status: 'cancelling', revision: 3 })
    await flushPromises()
    expect(useHuntStore().activeExecutions[7].status).toBe(status)
    expect(wrapper.findComponent({ name: 'HuntStepResults' }).props('step')).toEqual(finalStep)
    expect(mocks.showNotification).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(60000)
    expect(mocks.getExecution).toHaveBeenCalledTimes(reads)
    wrapper.unmount()
  },
)

it('suppresses an old cancellation failure after newer durable completion', async () => {
  const wrapper = await mountExecution('running', 42, { revision: 2 })
  let fail
  mocks.cancelExecution.mockReturnValueOnce(
    new Promise((_resolve, reject) => {
      fail = reject
    }),
  )
  await wrapper
    .findAll('button')
    .find((button) => button.text().includes('Cancel'))
    .trigger('click')
  mocks.getExecution.mockResolvedValue({ ...mocks.execution, status: 'completed', revision: 5 })
  await vi.advanceTimersByTimeAsync(1000)
  fail(new Error('Obsolete cancellation failure'))
  await flushPromises()
  expect(wrapper.text()).toContain('Completed')
  expect(wrapper.text()).not.toContain('Obsolete cancellation failure')
  expect(mocks.showNotification).not.toHaveBeenCalled()
  expect(useHuntStore().cancellationPending[7]).toBeUndefined()
  wrapper.unmount()
})
