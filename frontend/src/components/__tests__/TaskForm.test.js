import { expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import TaskForm from '../tasks/TaskForm.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useTaskStore } from '@/stores/taskStore'
import { caseService } from '@/services/case'

vi.mock('@/services/case', () => ({ caseService: { getCases: vi.fn() } }))

it('validates and submits new tasks by keyboard, then blocks submissions while saving', async () => {
  const pinia = createPinia()
  vi.spyOn(useTaskStore(pinia), 'loadTemplates').mockResolvedValue([])
  caseService.getCases.mockResolvedValue([{ id: 7, title: 'Investigation' }])
  await useActiveCaseStore(pinia).initialize()
  const wrapper = mountWithVuetify(TaskForm, { global: { plugins: [pinia] } })
  await flushPromises()
  expect(wrapper.findAll('label').some((label) => label.text() === 'Case')).toBe(false)
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

it('retains the owner during editing and blocks submission after a context switch', async () => {
  const pinia = createPinia()
  vi.spyOn(useTaskStore(pinia), 'loadTemplates').mockResolvedValue([])
  caseService.getCases.mockResolvedValue([{ id: 7 }, { id: 8 }])
  const context = useActiveCaseStore(pinia)
  await context.initialize(7)
  const wrapper = mountWithVuetify(TaskForm, {
    props: { task: { id: 1, case_id: 7, title: 'Review', description: 'Evidence' } },
    global: { plugins: [pinia] },
  })
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')[0][0]).toMatchObject({ case_id: 7 })
  await context.select(8)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('save')).toHaveLength(1)
})
