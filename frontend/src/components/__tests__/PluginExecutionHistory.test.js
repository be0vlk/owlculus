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
