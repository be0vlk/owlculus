import { beforeEach, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import ManageUsersModal from '../ManageUsersModal.vue'
import UserManagementCard from '../UserManagementCard.vue'
import { userService } from '@/services/user'
import { caseService } from '@/services/case'
import { useAuthStore } from '@/stores/auth'
import StrixyChat from '@/views/StrixyChat.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { strixyService } from '@/services/strixy'

vi.mock('@/services/strixy', () => ({ strixyService: { getAvailability: vi.fn() } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('@/services/user', () => ({ userService: { getUsers: vi.fn() } }))
vi.mock('@/services/case', () => ({
  caseService: {
    addUserToCase: vi.fn().mockResolvedValue({}),
    removeUserFromCase: vi.fn().mockResolvedValue({}),
  },
}))
const strixy = {
  id: 2,
  username: 'strixy_ai_1',
  email: 'strixy_ai_1@system.invalid',
  system_identity: 'strixy',
  role: 'Analyst',
  is_active: true,
}

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().user = { id: 1, role: 'Admin', is_superadmin: true }
  userService.getUsers.mockResolvedValue([strixy])
})

it('marks the permanent AI account and hides human account actions', async () => {
  const wrapper = mountWithVuetify(UserManagementCard)
  await flushPromises()
  expect(wrapper.text()).toContain('Strixy (AI)')
  expect(wrapper.find('[aria-label="Edit strixy_ai_1"]').exists()).toBe(false)
  expect(wrapper.find('[aria-label="More actions for strixy_ai_1"]').exists()).toBe(false)
})

it('assigns Strixy as an Analyst through the membership controls and removes it', async () => {
  const wrapper = mountWithVuetify(ManageUsersModal, {
    props: { show: false, caseId: 9, caseData: { users: [] } },
    attachTo: document.body,
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  const select = wrapper.findComponent({ name: 'VSelect' })
  expect(select.props('items')[0].displayText).toContain('Strixy (AI)')
  select.vm.$emit('update:modelValue', 2)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'VCheckbox' }).props('disabled')).toBe(true)
  let dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  await dialog
    .findAll('button')
    .find((button) => button.text() === 'Add User')
    .trigger('click')
  await flushPromises()
  expect(caseService.addUserToCase).toHaveBeenCalledWith(9, 2, false)
  await wrapper.setProps({ caseData: { users: [strixy] } })
  dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('Strixy (AI)')
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  await dialog.get('[aria-label="Remove strixy_ai_1@system.invalid from case"]').trigger('click')
  await flushPromises()
  expect(caseService.removeUserFromCase).toHaveBeenCalledWith(9, 2)
})

it('explains missing assignment on the chat page and recovers after assignment', async () => {
  const activeCase = useActiveCaseStore()
  Object.assign(activeCase, {
    initialized: true,
    accessibleCases: [{ id: 9, case_number: 'CASE-9' }],
  })
  activeCase.resolve(9)
  strixyService.getAvailability.mockRejectedValueOnce({
    response: {
      status: 403,
      data: {
        code: 'strixy_not_assigned',
        detail: 'Strixy is not assigned to this case. Ask an administrator to assign Strixy.',
      },
    },
  })
  const wrapper = mountWithVuetify({
    components: { StrixyChat },
    template: '<v-app><StrixyChat /></v-app>',
  })
  await flushPromises()
  expect(wrapper.find('h1').text()).toBe('Strixy')
  expect(wrapper.text()).toContain('CASE-9')
  expect(wrapper.text()).toContain('Strixy is not assigned to this case')
  expect(wrapper.get('[aria-label="Message input"]').element.disabled).toBe(true)
  strixyService.getAvailability.mockResolvedValueOnce({ is_configured: true })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Check again')
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('Strixy is not assigned')
  expect(wrapper.get('[aria-label="Message input"]').element.disabled).toBe(false)
})
