import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import HuntParameterForm from '../hunts/HuntParameterForm.vue'

it('accepts zero, preserves defaults, and renders multiline and server errors accessibly', async () => {
  const wrapper = mountWithVuetify(HuntParameterForm, {
    props: {
      parameters: {
        limit: { type: 'number', required: true, min: 0, default: 0 },
        notes: { type: 'string', multiline: true, default: 'Investigation notes' },
      },
      modelValue: {},
    },
  })
  await flushPromises()
  expect(await wrapper.vm.validate()).toBe(true)
  expect(wrapper.get('textarea').element.value).toBe('Investigation notes')
  await wrapper.setProps({ errors: { limit: 'Limit unavailable' } })
  await flushPromises()
  expect(wrapper.text()).toContain('Limit unavailable')
  expect(wrapper.get('input[type="number"]').attributes('aria-invalid')).toBe('true')
})

it('validates before execution, submits defaults, and retains failure feedback while open', async () => {
  const { default: HuntExecutionModal } = await import('../hunts/HuntExecutionModal.vue')
  const { DOMWrapper } = await import('@vue/test-utils')
  const wrapper = mountWithVuetify(HuntExecutionModal, {
    props: {
      modelValue: false,
      caseId: 4,
      hunt: {
        id: 7,
        display_name: 'Domain Hunt',
        initial_parameters: {
          domain: { type: 'string', required: true },
          limit: { type: 'number', default: 0 },
        },
      },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('execute')).toBeUndefined()
  expect(dialog.text()).toContain('Domain is required')
  await dialog.get('input[type="text"]').setValue('example.org')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('execute')).toEqual([
    [{ huntId: 7, caseId: 4, parameters: { domain: 'example.org', limit: 0 } }],
  ])
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  await wrapper.setProps({ executing: true })
  expect(dialog.get('button[aria-label="Close hunt configuration"]').element.disabled).toBe(true)
  await wrapper.setProps({ executing: false, error: 'Execution unavailable' })
  expect(
    dialog
      .findAll('[role="alert"]')
      .some((alert) => alert.text().includes('Execution unavailable')),
  ).toBe(true)
  expect(dialog.get('input[type="text"]').element.value).toBe('example.org')
})

it('has no case selector and blocks execution without resolved context', async () => {
  const { default: HuntExecutionModal } = await import('../hunts/HuntExecutionModal.vue')
  const { DOMWrapper } = await import('@vue/test-utils')
  const wrapper = mountWithVuetify(HuntExecutionModal, {
    props: { modelValue: false, hunt: { id: 7 } },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.find('input[role="combobox"]').exists()).toBe(false)
  expect(dialog.get('button[type="submit"]').element.disabled).toBe(true)
  await dialog.get('form').trigger('submit')
  expect(wrapper.emitted('execute')).toBeUndefined()
})
