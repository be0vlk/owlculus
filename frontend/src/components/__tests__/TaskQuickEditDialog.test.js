import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import TaskQuickEditDialog from '../tasks/TaskQuickEditDialog.vue'
import { createPinia } from 'pinia'

let wrapper
it('validates required custom fields and submits quick edits from the keyboard', async () => {
  wrapper = mountWithVuetify(TaskQuickEditDialog, {
    props: {
      task: { id: 1, title: 'Review', status: 'pending', custom_fields: { result: '' } },
      customFields: [{ name: 'result', label: 'Result', type: 'string', required: true }],
    },
    global: { plugins: [createPinia()] },
  })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toBeUndefined()
  expect(wrapper.text()).toContain('Result is required')
  const label = wrapper.findAll('label').find((label) => label.text() === 'Result')
  const result = wrapper.get(`[id="${label.attributes('for')}"]`)
  await result.setValue('Verified')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toEqual([[{ custom_fields: { result: 'Verified' } }]])
  await wrapper.setProps({ saving: true })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toHaveLength(1)
  expect(result.attributes('disabled')).toBeDefined()
})
