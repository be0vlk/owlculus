import { expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import TaskForm from '../tasks/TaskForm.vue'
import { useTaskStore } from '@/stores/taskStore'
import { caseService } from '@/services/case'

vi.mock('@/services/case', () => ({ caseService: { getCases: vi.fn() } }))

it('validates and submits new tasks by keyboard, then blocks submissions while saving', async () => {
  const pinia = createPinia()
  vi.spyOn(useTaskStore(pinia), 'loadTemplates').mockResolvedValue([])
  caseService.getCases.mockResolvedValue([{ id: 7, title: 'Investigation' }])
  const wrapper = mountWithVuetify(TaskForm, { props: { caseId: 7 }, global: { plugins: [pinia] } })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toBeUndefined()
  expect(wrapper.text()).toContain('Title is required')
  const titleLabel = wrapper.findAll('label').find((label) => label.text() === 'Title')
  await wrapper.get(`[id="${titleLabel.attributes('for')}"]`).setValue('Review')
  await wrapper.get('textarea').setValue('Review evidence')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')[0][0]).toMatchObject({
    case_id: 7,
    title: 'Review',
    description: 'Review evidence',
  })
  await wrapper.setProps({ saving: true })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toHaveLength(1)
})
