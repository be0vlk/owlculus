import { expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import AddUserToCaseModal from '../AddUserToCaseModal.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))

it('offers the permanent AI Analyst even after a full page of existing humans', async () => {
  setActivePinia(createPinia())
  const humans = Array.from({ length: 100 }, (_, id) => ({
    id: id + 1,
    username: `human_${id}`,
    email: `human_${id}@example.com`,
    role: 'Analyst',
  }))
  api.get.mockResolvedValueOnce({ data: humans }).mockResolvedValueOnce({
    data: [
      {
        id: 101,
        username: 'strixy',
        email: 'strixy@system.invalid',
        system_identity: 'strixy',
        role: 'Analyst',
      },
    ],
  })
  const wrapper = mountWithVuetify(AddUserToCaseModal, {
    props: { show: false, caseId: 9 },
    attachTo: document.body,
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  const items = wrapper.findComponent({ name: 'VSelect' }).props('items')
  expect(items).toHaveLength(101)
  expect(items[100].displayText).toContain('Strixy (AI)')
  expect(api.get).toHaveBeenLastCalledWith('/api/users/', { params: { skip: 100, limit: 100 } })
})
