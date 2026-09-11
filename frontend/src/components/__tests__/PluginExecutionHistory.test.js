import { expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import PluginExecutionHistory from '../plugins/PluginExecutionHistory.vue'
import PluginResultsModal from '../plugins/PluginResultsModal.vue'
import { pluginService } from '@/services/plugin'

vi.mock('@/services/plugin', () => ({
  pluginService: {
    getHistory: vi.fn(),
    executePlugin: vi.fn(),
    getExecution: vi.fn(),
    getResults: vi.fn(),
    cancelExecution: vi.fn(),
  },
}))

it('reopens a failed run from case history after reload with retained typed results', async () => {
  const saved = {
    id: 12,
    plugin_name: 'ExamplePlugin',
    status: 'failed',
    created_at: '2026-09-05T00:00:00Z',
    parameters: { query: 'owl' },
    error: { message: 'Provider unavailable' },
  }
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockResolvedValue({
    items: [{ type: 'data', data: { query: 'owl' } }],
    cursor: 3,
  })
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  await wrapper.get('.v-list-item').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('failed')
  expect(wrapper.get('[role="alert"]').text()).toContain('Provider unavailable')
  expect(wrapper.findComponent(PluginResultsModal).props('results')).toEqual([
    { type: 'data', data: { query: 'owl' } },
  ])
  await wrapper.setProps({ caseId: 8 })
  await flushPromises()
  expect(wrapper.find('[aria-label="Selected plugin execution"]').exists()).toBe(false)
  wrapper.unmount()
})

it('shows why accepted work is waiting with acceptance and dispatch times', async () => {
  const saved = {
    id: 14,
    plugin_name: 'ExamplePlugin',
    status: 'queued',
    created_at: '2026-09-05T00:00:00Z',
    last_dispatch_at: '2026-09-05T00:00:02Z',
    next_dispatch_at: '2026-09-05T00:00:05Z',
    waiting_reason: 'Background broker unavailable; dispatch will retry',
  }
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockResolvedValue({ items: [], cursor: 0 })
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  await wrapper.get('.v-list-item').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain(saved.waiting_reason)
  expect(wrapper.text()).toContain('Accepted')
  expect(wrapper.text()).toContain('Last dispatch attempt')
  expect(wrapper.text()).toContain('Next retry')
  wrapper.unmount()
})

it('offers an explicit cancel control and waits for confirmed cleanup', async () => {
  const saved = {
    id: 18,
    plugin_name: 'ExamplePlugin',
    status: 'running',
    created_at: '2026-09-05T00:00:00Z',
  }
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockResolvedValue({ items: [], cursor: 0 })
  pluginService.cancelExecution.mockResolvedValue({ ...saved, status: 'cancelling' })
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  await wrapper.get('.v-list-item').trigger('click')
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Cancel execution')
    .trigger('click')
  await flushPromises()
  expect(pluginService.cancelExecution).toHaveBeenCalledWith(18)
  expect(wrapper.text()).toContain('Waiting for execution cleanup')
  expect(wrapper.findAll('button').some((button) => button.text() === 'Cancel execution')).toBe(
    false,
  )
  wrapper.unmount()
})

it('reopens recovery waiting and then an uncertain failure without resubmitting', async () => {
  const saved = {
    id: 19,
    plugin_name: 'ExamplePlugin',
    status: 'running',
    dispatch_state: 'recovery_waiting',
    waiting_reason: 'Worker interrupted; waiting for cleanup and safe recovery',
    created_at: '2026-09-05T00:00:00Z',
  }
  const retained = [{ type: 'data', data: { query: 'owl' } }]
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockResolvedValue({ items: retained, cursor: 1 })
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  expect(wrapper.get('.v-list-item').text()).toContain('Recovery waiting')
  await wrapper.get('.v-list-item').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain(saved.waiting_reason)
  const failed = {
    ...saved,
    status: 'failed',
    dispatch_state: 'published',
    waiting_reason: null,
    error: {
      code: 'interrupted_uncertain_outcome',
      message:
        'External work may have occurred; review retained output before submitting a new run.',
    },
  }
  pluginService.getExecution.mockResolvedValue(failed)
  await wrapper.get('.v-list-item').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain(failed.error.message)
  expect(wrapper.findComponent(PluginResultsModal).props('results')).toEqual(retained)
  expect(pluginService.executePlugin).not.toHaveBeenCalled()
  wrapper.unmount()
})

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@/utils/download', () => ({ downloadBlob: vi.fn() }))

it('follows an empty filtered page and rechecks authorization before exporting', async () => {
  const { downloadBlob } = await import('@/utils/download')
  const saved = {
    id: 21,
    plugin_name: 'CorrelationScan',
    status: 'completed',
    created_at: '2026-09-05T00:00:00Z',
  }
  const visible = { type: 'data', data: { entity_name: 'Readable', matches: [] } }
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockImplementation(async (_id, cursor) =>
    cursor === 0
      ? { items: [], cursor: 1, next_cursor: 1 }
      : { items: [visible], cursor: 2, next_cursor: null },
  )
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  await wrapper.get('.v-list-item').trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.findComponent(PluginResultsModal).props('results')).toEqual([visible]),
  )
  // Membership changed after the visible page was loaded.
  pluginService.getResults.mockResolvedValue({
    items: [{ type: 'complete', data: {} }],
    cursor: 2,
    next_cursor: null,
  })
  wrapper
    .findComponent(PluginResultsModal)
    .vm.$emit('export', { pluginName: 'CorrelationScan', results: [visible] })
  await flushPromises()
  const blob = downloadBlob.mock.calls.at(-1)[0].blob
  const text = await new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.readAsText(blob)
  })
  expect(text).not.toContain('Readable')
  expect(text).toContain('complete')
  downloadBlob.mockClear()
  pluginService.getExecution.mockRejectedValue({
    response: { status: 403, data: { detail: 'Not authorized' } },
  })
  wrapper
    .findComponent(PluginResultsModal)
    .vm.$emit('export', { pluginName: 'CorrelationScan', results: [visible] })
  await flushPromises()
  expect(downloadBlob).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('reopens and exports continued email matches after hidden-only pages without duplicate fields', async () => {
  const { downloadBlob } = await import('@/utils/download')
  const saved = {
    id: 31,
    plugin_name: 'CorrelationScan',
    status: 'failed',
    created_at: '2026-09-07T00:00:00Z',
    error: { message: 'Available results are partial.' },
  }
  const part = (related, fields) => ({
    type: 'data',
    data: {
      case_id: 7,
      entity_id: 10,
      entity_name: 'Ada',
      entity_type: 'person',
      match_type: 'email',
      group_id: 'email-group',
      continuation: 'merge',
      matches: [
        {
          case_id: 8,
          entity_id: related,
          entity_name: `Related ${related}`,
          signal: 'Exact email match',
          signal_rank: 0,
          fields,
        },
      ],
    },
  })
  const first = part(21, [{ field: 'email', value: 'ada@example.com' }])
  const second = part(22, [{ field: 'email', value: 'ada@example.com' }])
  const repeated = part(21, [{ field: 'usernames[0]', value: 'ada@example.com' }])
  pluginService.getHistory.mockResolvedValue({ items: [saved], next_cursor: null })
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockImplementation(async (_id, cursor) => {
    if (cursor === 0) return { items: [], cursor: 1, next_cursor: 1 }
    if (cursor === 1) return { items: [first], cursor: 2, next_cursor: 2 }
    return { items: [second, repeated], cursor: 4, next_cursor: null }
  })
  const wrapper = mountWithVuetify(PluginExecutionHistory, { props: { caseId: 7 } })
  await flushPromises()
  await wrapper.get('.v-list-item').trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.findComponent(PluginResultsModal).props('results')).toHaveLength(3),
  )
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'View retained results')
    .trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.findComponent(PluginResultsModal).props('results')).toHaveLength(3),
  )
  wrapper.findComponent(PluginResultsModal).vm.$emit('export', { pluginName: 'CorrelationScan' })
  await flushPromises()
  const blob = downloadBlob.mock.calls.at(-1)[0].blob
  const text = await new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.readAsText(blob)
  })
  const exported = JSON.parse(text)
  expect(exported.partial).toBe(true)
  expect(exported.error).toBe(saved.error.message)
  expect(exported.results).toHaveLength(1)
  expect(exported.results[0].data.matches.map((match) => match.entity_id)).toEqual([21, 22])
  expect(exported.results[0].data.matches[0].fields).toEqual([
    { field: 'email', value: 'ada@example.com' },
    { field: 'usernames[0]', value: 'ada@example.com' },
  ])
  wrapper.unmount()
})

it('keeps a loaded prefix and an in-dialog retry after a later page fails', async () => {
  const { DOMWrapper } = await import('@vue/test-utils')
  const { default: PluginExecutionViewer } = await import('../plugins/PluginExecutionViewer.vue')
  const saved = {
    id: 41,
    plugin_name: 'CorrelationScan',
    status: 'completed',
    created_at: '2026-09-07T00:00:00Z',
  }
  const visible = {
    type: 'data',
    data: {
      case_id: 1,
      entity_id: 10,
      entity_name: 'Readable prefix',
      match_type: 'email',
      matches: [{ case_id: 2, entity_id: 20, entity_name: 'Related' }],
    },
  }
  pluginService.getExecution.mockResolvedValue(saved)
  pluginService.getResults.mockImplementation(async (_id, cursor) => {
    if (!cursor) return { items: [visible], cursor: 1, next_cursor: 1 }
    throw new Error('network')
  })
  const wrapper = mountWithVuetify(PluginExecutionViewer, {
    props: { executionId: 41 },
    attachTo: document.body,
  })
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === 'View retained results')
    .trigger('click')
  await vi.waitFor(() =>
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Retry retrieval'),
  )
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('Readable prefix')
  expect(dialog.text()).toContain('Partial retained results')
  expect(dialog.text()).not.toContain('Correlation scan complete')
  pluginService.getResults.mockImplementation(async (_id, cursor) =>
    cursor === 0
      ? { items: [visible], cursor: 1, next_cursor: 1 }
      : { items: [{ type: 'complete', data: {} }], cursor: 2, next_cursor: null },
  )
  await dialog
    .findAll('button')
    .find((b) => b.text() === 'Retry retrieval')
    .trigger('click')
  await vi.waitFor(() => expect(dialog.text()).toContain('Correlation scan complete'))
  expect(dialog.findAll('h3').filter((h) => h.text() === 'Readable prefix')).toHaveLength(1)
  expect(dialog.text()).not.toContain('Retry retrieval')
  wrapper.unmount()
})
