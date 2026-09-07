import { expect, it, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import { VForm } from 'vuetify/components'
import CorrelationScanPluginResult from '../plugins/CorrelationScanPluginResult.vue'
import GenericPluginParams from '../plugins/GenericPluginParams.vue'
import PluginResultsModal from '../plugins/PluginResultsModal.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@/composables/usePluginApiKeys', () => ({
  usePluginApiKeys: () => ({ checkPluginApiKeys: vi.fn(), getMissingApiKeys: () => [] }),
}))

it('validates generic required fields without rendering plugin metadata as inputs', async () => {
  const wrapper = mountWithVuetify(VForm, {
    slots: {
      default: {
        components: { GenericPluginParams },
        template: `<GenericPluginParams :model-value="{}" :parameters="{ query: { type: 'string', required: true, label: 'Search query' }, api_key_requirements: [] }" />`,
      },
    },
  })
  await flushPromises()
  expect(wrapper.findAll('input')).toHaveLength(1)
  expect((await wrapper.vm.validate()).valid).toBe(false)
  expect(wrapper.text()).toContain('Search query is required')
  await wrapper.get('input').setValue('example.org')
  expect((await wrapper.vm.validate()).valid).toBe(true)
})

it('shows structured results, exports them, and closes through an accessible action', async () => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: {
      modelValue: false,
      pluginName: 'ExamplePlugin',
      results: { matches: ['example.org'] },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('example.org')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  expect(wrapper.emitted('export')[0][0].results).toEqual({ matches: ['example.org'] })
  await dialog.get('button[aria-label="Close plugin results"]').trigger('click')
  expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
})

it.each([[], {}, null])('shows an explicit empty result state for %j', async (results) => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: { modelValue: false, pluginName: 'ExamplePlugin', results },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('No Results Available')
  await wrapper.setProps({ error: 'Execution failed' })
  expect(dialog.text()).toContain('Execution failed')
})

it('explains a completed correlation scan with no matches', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: { result: [{ type: 'complete', data: {} }] },
  })
  expect(wrapper.get('[role="alert"]').text()).toBe(
    'Correlation scan complete. No correlations are available in accessible Cases.',
  )
})

it('does not describe a failed correlation scan as a successful empty result', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        { type: 'error', data: { message: 'Case not found' } },
        { type: 'complete', data: {} },
      ],
    },
  })
  expect(wrapper.get('[role="alert"]').text()).toBe('Case not found')
  expect(wrapper.text()).not.toContain('No correlations found')
  expect(wrapper.text()).not.toContain('Correlation scan complete')
})

it('offers optional saving for correlation without source or destination selectors', async () => {
  const { default: CorrelationScanPluginParams } = await import(
    '../plugins/CorrelationScanPluginParams.vue'
  )
  const wrapper = mountWithVuetify(CorrelationScanPluginParams, {
    props: { parameters: {}, modelValue: { save_to_case: false, case_id: 999 } },
  })
  await flushPromises()
  expect(wrapper.findAll('input')).toHaveLength(1)
  const toggle = wrapper.get('input[type="checkbox"]')
  expect(toggle.element.checked).toBe(false)
  await toggle.setValue(true)
  expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({ save_to_case: true })
  expect(wrapper.text()).not.toContain('Case to Scan')
  expect(wrapper.text()).not.toContain('Case to Save')
})

it('renders retained typed events through the specialized correlation renderer', async () => {
  const { default: PluginResult } = await import('../plugins/PluginResult.vue')
  const wrapper = mountWithVuetify(PluginResult, {
    props: { pluginName: 'CorrelationScan', result: [{ type: 'complete', data: {} }] },
  })
  await vi.waitFor(() =>
    expect(wrapper.findComponent(CorrelationScanPluginResult).exists()).toBe(true),
  )
  expect(wrapper.text()).toContain('Correlation scan complete')
})

it('labels retained partial output and preserves its failure in exports', async () => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: {
      modelValue: false,
      pluginName: 'ExamplePlugin',
      results: [{ type: 'data', data: { match: 'example.org' } }],
      error: 'Output exceeds the operation limit',
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('Partial retained results')
  expect(dialog.text()).toContain('Output exceeds the operation limit')
  expect(dialog.text()).toContain('example.org')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  expect(wrapper.emitted('export')[0][0]).toMatchObject({
    partial: true,
    error: 'Output exceeds the operation limit',
  })
})
