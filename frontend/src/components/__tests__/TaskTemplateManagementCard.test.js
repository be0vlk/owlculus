import { beforeEach, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import TaskTemplateManagementCard from '../TaskTemplateManagementCard.vue'
import { taskService } from '@/services/task'

vi.mock('@/services/task', () => ({
  taskService: {
    getTemplates: vi.fn(),
    createCustomTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
  },
}))

const existing = () => ({
  id: 1,
  name: 'review',
  display_name: 'Review',
  description: 'Review evidence',
  category: 'Review',
  is_active: true,
  definition_json: { fields: [{ name: 'source', label: 'Source', type: 'string' }] },
})
const body = () => new DOMWrapper(document.body)
const button = (name) =>
  body()
    .findAll('button')
    .find((item) => item.text().trim() === name)
const dialogInputs = () => body().findAll('.v-overlay__content input')

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'error').mockImplementation(() => {})
  taskService.getTemplates.mockResolvedValue([existing()])
})

async function mountCard() {
  const wrapper = mountWithVuetify(TaskTemplateManagementCard, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

it('loads templates including inactive ones', async () => {
  const wrapper = await mountCard()
  expect(taskService.getTemplates).toHaveBeenCalledWith(true)
  expect(wrapper.text()).toContain('Review')
  expect(wrapper.text()).toContain('1 fields')
})

it('creates a template from a blank form and rejects an existing name', async () => {
  taskService.createCustomTemplate.mockImplementation(async (template) => ({ ...template, id: 2 }))
  const wrapper = await mountCard()
  await button('Add Template').trigger('click')
  await flushPromises()
  const [name, displayName, , category] = dialogInputs()
  await name.setValue('review')
  await displayName.setValue('Triage')
  await body().get('.v-overlay__content textarea').setValue('Triage incoming leads')
  await category.setValue('Analysis')
  await button('Create Template').trigger('click')
  await flushPromises()
  expect(body().text()).toContain('Template name already exists')
  expect(taskService.createCustomTemplate).not.toHaveBeenCalled()

  await name.setValue('triage')
  await button('Create Template').trigger('click')
  await flushPromises()
  expect(taskService.createCustomTemplate).toHaveBeenCalledWith({
    name: 'triage',
    display_name: 'Triage',
    description: 'Triage incoming leads',
    category: 'Analysis',
    is_active: true,
    definition_json: { fields: [] },
  })
  expect(wrapper.emitted('notification').at(-1)[0].color).toBe('success')
  expect(wrapper.text()).toContain('Triage')

  await button('Add Template').trigger('click')
  await flushPromises()
  expect(dialogInputs()[0].element.value).toBe('')
})

it('edits a copy of the template and sends the update', async () => {
  taskService.updateTemplate.mockImplementation(async (id, updates) => ({ ...updates, id }))
  const wrapper = await mountCard()
  await wrapper.get('[aria-label="Edit Review"]').trigger('click')
  await flushPromises()
  expect(body().text()).toContain('Edit Task Template - Review')
  expect(dialogInputs()[0].element.disabled).toBe(true)
  await dialogInputs()[1].setValue('Peer review')
  await button('Update Template').trigger('click')
  await flushPromises()
  const { id, ...template } = existing()
  expect(taskService.updateTemplate).toHaveBeenCalledWith(id, {
    ...template,
    display_name: 'Peer review',
  })
  expect(wrapper.text()).toContain('Peer review')
})

it('asks the dashboard to confirm deletion before deleting', async () => {
  const wrapper = await mountCard()
  await wrapper.get('[aria-label="Delete Review"]').trigger('click')
  const [{ onConfirm }] = wrapper.emitted('confirmDelete').at(-1)
  expect(taskService.deleteTemplate).not.toHaveBeenCalled()
  await onConfirm()
  await flushPromises()
  expect(taskService.deleteTemplate).toHaveBeenCalledWith(1)
  expect(wrapper.text()).toContain('No Task Templates')
})
