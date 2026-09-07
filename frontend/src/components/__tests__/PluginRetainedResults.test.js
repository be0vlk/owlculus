import { afterEach, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import PluginExecutionViewer from '../plugins/PluginExecutionViewer.vue'
import { pluginService } from '@/services/plugin'
import { downloadBlob } from '@/utils/download'

vi.mock('@/services/plugin', () => ({
  pluginService: {
    getExecution: vi.fn(),
    getResults: vi.fn(),
    cancelExecution: vi.fn(),
  },
}))
vi.mock('@/utils/download', () => ({ downloadBlob: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const state = (id = 1, status = 'completed') => ({
  id,
  status,
  plugin_name: 'CorrelationScan',
  created_at: '2026-09-07T00:00:00Z',
  parameters: { query: `Source ${id}` },
})
const result = (name = 'Readable') => ({
  type: 'data',
  data: {
    case_id: 1,
    entity_id: 10,
    entity_name: name,
    match_type: 'email',
    matches: [{ case_id: 2, entity_id: 20, entity_name: 'Related' }],
  },
})
const page = (items) => ({ items, cursor: 2, next_cursor: null })
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const button = (wrapper, text) => wrapper.findAll('button').find((b) => b.text() === text)
const dialog = () => new DOMWrapper(document.querySelector('[role="dialog"]'))
let wrapper
async function open() {
  wrapper = mountWithVuetify(PluginExecutionViewer, {
    props: { executionId: 1 },
    attachTo: document.body,
  })
  await flushPromises()
  await button(wrapper, 'View retained results').trigger('click')
  await flushPromises()
}
afterEach(() => {
  wrapper?.unmount()
  vi.resetAllMocks()
  vi.useRealTimers()
})

it('shows loading until a delayed first page arrives, even with durable completion', async () => {
  pluginService.getExecution.mockResolvedValue(state())
  const pending = deferred()
  pluginService.getResults.mockReturnValue(pending.promise)
  await open()
  expect(dialog().text()).toContain('Loading retained results')
  expect(dialog().text()).not.toContain('No correlations are available')
  pending.resolve(page([{ type: 'complete', data: {} }]))
  await vi.waitFor(() => expect(dialog().text()).toContain('No correlations are available'))
})

it.each(['failed', 'cancelled'])(
  'distinguishes durable %s from a completed empty scan',
  async (status) => {
    pluginService.getExecution.mockResolvedValue({
      ...state(1, status),
      error: status === 'failed' ? { message: 'Provider failed' } : null,
    })
    pluginService.getResults.mockResolvedValue(page([{ type: 'complete', data: {} }]))
    await open()
    await vi.waitFor(() => expect(dialog().text()).toContain(status))
    expect(dialog().text()).not.toContain('Correlation scan complete')
    expect(dialog().text()).not.toContain('No correlations are available')
  },
)

it('shows export page failure in the dialog without losing readable content or downloading a prefix', async () => {
  pluginService.getExecution.mockResolvedValue(state())
  pluginService.getResults.mockResolvedValue(page([result()]))
  await open()
  await vi.waitFor(() => expect(dialog().text()).toContain('Readable'))
  pluginService.getResults
    .mockResolvedValueOnce({ items: [result()], cursor: 1, next_cursor: 1 })
    .mockRejectedValueOnce(new Error('offline'))
  await button(dialog(), 'Export').trigger('click')
  await flushPromises()
  expect(dialog().text()).toContain('Could not export current results')
  expect(dialog().text()).toContain('Readable')
  expect(dialog().text()).not.toContain('Plugin execution failed')
  expect(downloadBlob).not.toHaveBeenCalled()
})

it.each(['retrieval', 'export'])(
  'clears inaccessible content after authorization loss during %s',
  async (operation) => {
    pluginService.getExecution.mockResolvedValue(state(1, 'running'))
    pluginService.getResults.mockResolvedValue(page([result('Restricted detail')]))
    await open()
    await vi.waitFor(() => expect(dialog().text()).toContain('Restricted detail'))
    pluginService.getResults.mockRejectedValue({
      response: { status: 403, data: { detail: 'Not authorized' } },
    })
    if (operation === 'export') await button(dialog(), 'Export').trigger('click')
    await vi.waitFor(() => expect(dialog().text()).not.toContain('Restricted detail'), {
      timeout: 2500,
    })
    expect(dialog().text()).not.toContain('Source 1')
    expect(downloadBlob).not.toHaveBeenCalled()
  },
)

it.each(['resolve', 'reject'])(
  'ignores an obsolete export %s after switching executions',
  async (outcome) => {
    pluginService.getExecution.mockImplementation(async (id) => state(id))
    pluginService.getResults.mockResolvedValue(page([result('Old content')]))
    await open()
    const pending = deferred()
    pluginService.getResults.mockReturnValueOnce(pending.promise)
    await button(dialog(), 'Export').trigger('click')
    await flushPromises()
    pluginService.getResults.mockResolvedValue(page([result('New content')]))
    await wrapper.setProps({ executionId: 2 })
    await flushPromises()
    await button(wrapper, 'View retained results').trigger('click')
    await flushPromises()
    pending[outcome](
      outcome === 'resolve' ? page([result('Old content')]) : { response: { status: 403 } },
    )
    await flushPromises()
    await vi.waitFor(() => expect(dialog().text()).toContain('New content'))
    expect(dialog().text()).not.toContain('Old content')
    expect(dialog().text()).not.toContain('Could not export')
    expect(downloadBlob).not.toHaveBeenCalled()
  },
)

it('ignores a delayed result page after switching executions', async () => {
  pluginService.getExecution.mockImplementation(async (id) => state(id))
  const pending = deferred()
  pluginService.getResults.mockReturnValue(pending.promise)
  await open()
  pluginService.getResults.mockResolvedValue(page([result('New content')]))
  await wrapper.setProps({ executionId: 2 })
  await flushPromises()
  await button(wrapper, 'View retained results').trigger('click')
  pending.resolve(page([result('Old content')]))
  await flushPromises()
  await vi.waitFor(() => expect(dialog().text()).toContain('New content'))
  expect(dialog().text()).not.toContain('Old content')
})
