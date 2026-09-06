import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import ActiveCaseSwitcher from '../ActiveCaseSwitcher.vue'
import { useActiveCaseStore } from '../../stores/activeCase'
import { useAuthStore } from '../../stores/auth'
import { caseService } from '../../services/case'
import { mountWithVuetify } from './helpers/vuetify'

vi.mock('../../services/case', () => ({ caseService: { getCases: vi.fn() } }))
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setActivePinia(createPinia())
  useAuthStore().user = { role: 'Investigator' }
})

it('announces loading and an empty accessible-case list with assignment guidance', async () => {
  let finish
  caseService.getCases.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const store = useActiveCaseStore()
  const pending = store.initialize()
  const wrapper = shallowMount(ActiveCaseSwitcher)
  expect(wrapper.get('[role="status"]').text()).toContain('Loading cases')
  finish([])
  await pending
  await flushPromises()
  expect(wrapper.text()).toContain('No accessible cases')
  expect(wrapper.text()).toContain('Contact an administrator')
})

it('shows failed resolution and offers a retry', async () => {
  caseService.getCases.mockRejectedValue(new Error('offline'))
  await useActiveCaseStore().initialize()
  const wrapper = shallowMount(ActiveCaseSwitcher, {
    global: {
      stubs: {
        VBtn: { template: '<button><slot /></button>' },
      },
    },
  })
  expect(wrapper.get('[role="alert"]').text()).toContain('Unable to load accessible cases')
  caseService.getCases.mockResolvedValue([])
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('No accessible cases')
})

const cases = [
  { id: 1, case_number: '2609-01', title: 'Missing person investigation', status: 'Open' },
  { id: 2, case_number: '2609-02', title: 'Archived fraud investigation', status: 'Closed' },
]

async function mountResolvedSwitcher() {
  caseService.getCases.mockResolvedValue(cases)
  await useActiveCaseStore().initialize(1)
  return mountWithVuetify(ActiveCaseSwitcher, { attachTo: document.body })
}

it('prevents free text entry and switches to an existing case from the menu', async () => {
  const wrapper = await mountResolvedSwitcher()
  const input = wrapper.get('input:not([type="hidden"])')
  await input.setValue('A made-up case')
  expect(input.element.value).not.toContain('A made-up case')
  expect(useActiveCaseStore().activeCaseId).toBe(1)

  await wrapper.get('.v-field').trigger('mousedown')
  await flushPromises()
  const option = [...document.querySelectorAll('.v-list-item')].find((element) =>
    element.textContent.includes(cases[1].title),
  )
  expect(option).toBeTruthy()
  expect(option.textContent).toContain(cases[1].case_number)
  expect(option.textContent).toContain(cases[1].status)
  option.click()
  await flushPromises()

  expect(useActiveCaseStore().activeCaseId).toBe(2)
  expect(wrapper.get('.active-case-summary').text()).toContain(cases[1].case_number)
  expect(wrapper.get('.active-case-summary').text()).toContain(cases[1].title)
  expect(wrapper.get('.active-case-summary').text()).toContain('Closed')
  expect(wrapper.get('[aria-live="polite"]').text()).toContain(cases[1].title)
})

it('opens with the keyboard and dismisses without changing the active case', async () => {
  const wrapper = await mountResolvedSwitcher()
  const input = wrapper.get('input:not([type="hidden"])')
  input.element.focus()
  await input.trigger('keydown', { key: 'ArrowDown' })
  await flushPromises()
  expect(input.attributes('aria-expanded')).toBe('true')

  await input.trigger('keydown', { key: 'Escape' })
  await flushPromises()
  expect(input.attributes('aria-expanded')).toBe('false')
  expect(useActiveCaseStore().activeCaseId).toBe(1)
})

it('disables switching while the accessible cases are being refreshed', async () => {
  const wrapper = await mountResolvedSwitcher()
  useActiveCaseStore().refreshing = true
  await flushPromises()
  expect(wrapper.get('input:not([type="hidden"])').element.disabled).toBe(true)
})
