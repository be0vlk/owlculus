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
