import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import TaskTemplateForm from '../TaskTemplateForm.vue'

let wrapper
it('publishes the latest template values before a keyboard submission', async () => {
  wrapper = mountWithVuetify(TaskTemplateForm, {
    props: {
      modelValue: {
        name: 'review',
        display_name: 'Review',
        description: 'Review evidence',
        category: 'Review',
        is_active: true,
        definition_json: { fields: [] },
      },
      validateTemplateName: () => true,
      validateDisplayName: () => true,
      validateDescription: () => true,
      validateCategory: () => true,
    },
  })
  await wrapper.findAll('input')[1].setValue('Updated review')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('update:modelValue').at(-1)[0].display_name).toBe('Updated review')
  expect(wrapper.emitted('submit')).toHaveLength(1)
})
