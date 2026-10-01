import { expect, it } from 'vitest'
import { reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import TaskTemplateForm from '../TaskTemplateForm.vue'

it('edits the bound template in place before a keyboard submission', async () => {
  const template = reactive({
    name: 'review',
    display_name: 'Review',
    description: 'Review evidence',
    category: 'Review',
    is_active: true,
    definition_json: { fields: [] },
  })
  const wrapper = mountWithVuetify(TaskTemplateForm, { props: { modelValue: template } })
  await wrapper.findAll('input')[1].setValue('Updated review')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(template.display_name).toBe('Updated review')
  expect(wrapper.emitted('submit')).toHaveLength(1)
})
