import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import ActiveCaseSwitcher from '../ActiveCaseSwitcher.vue'
import { useActiveCaseStore } from '../../stores/activeCase'
import { useAuthStore } from '../../stores/auth'
import { caseService } from '../../services/case'

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
