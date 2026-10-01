import { expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from '@/components/__tests__/helpers/vuetify'
import PluginsDashboard from '../PluginsDashboard.vue'
import { pluginService } from '@/services/plugin'

const activeCase = vi.hoisted(() => ({ activeCaseId: 7, ready: true }))
vi.mock('@/stores/activeCase', () => ({ useActiveCaseStore: () => activeCase }))

vi.mock('@/services/plugin', () => ({
  pluginService: { listPlugins: vi.fn(), executePlugin: vi.fn(), getHistory: vi.fn().mockResolvedValue({ items: [] }) },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ userRole: 'Analyst' }) }))
vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))

it('reads missing API keys from the plugin list without fetching key status', async () => {
  const { default: api } = await import('@/services/api')
  pluginService.listPlugins.mockResolvedValue({
    KeyedPlugin: {
      display_name: 'Keyed',
      enabled: true,
      api_key_requirements: ['shodan', 'virustotal'],
      api_key_status: { shodan: true, virustotal: false },
      parameters: { query: { type: 'string' } },
    },
  })
  const wrapper = mountWithVuetify(PluginsDashboard, {
    global: { stubs: { BaseDashboard: { template: '<main><slot /></main>' } } },
  })
  await flushPromises()
  await wrapper.get('button[aria-label="Configure Keyed"]').trigger('click')
  await flushPromises()
  const submit = wrapper.get('button[type="submit"]')
  expect(submit.text()).toContain('API Key Required')
  expect(submit.element.disabled).toBe(true)
  expect(wrapper.text()).toContain('requires an API key for: Virustotal')
  expect(api.get).not.toHaveBeenCalled()
})

it('validates keyboard submissions, disables pending requests, and permits retry after failure', async () => {
  pluginService.listPlugins.mockResolvedValue({
    ExamplePlugin: {
      display_name: 'Example',
      enabled: true,
      parameters: { query: { type: 'string', required: true } },
    },
  })
  const wrapper = mountWithVuetify(PluginsDashboard, {
    global: { stubs: { BaseDashboard: { template: '<main><slot /></main>' } } },
  })
  await flushPromises()
  await wrapper.get('button[aria-label="Configure Example"]').trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(pluginService.executePlugin).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('query is required')
  await wrapper.get('input').setValue('example.org')
  let rejectRequest
  pluginService.executePlugin.mockImplementationOnce(
    () =>
      new Promise((resolve, reject) => {
        rejectRequest = reject
      }),
  )
  vi.spyOn(console, 'error').mockImplementation(() => {})
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(pluginService.executePlugin).toHaveBeenCalledWith(
    'ExamplePlugin',
    {
      query: 'example.org',
    },
    7,
  )
  expect(wrapper.get('button[type="submit"]').element.disabled).toBe(true)
  expect(wrapper.get('input').element.disabled).toBe(true)
  rejectRequest(new Error('Service unavailable'))
  await flushPromises()
  expect(wrapper.text()).toContain('Service unavailable')
  expect(wrapper.get('input').element.value).toBe('example.org')
  expect(wrapper.get('button[type="submit"]').element.disabled).toBe(false)
})
