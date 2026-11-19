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

it('enables and disables Strixy through the case switch, not the member list', async () => {
  const wrapper = mountWithVuetify(ManageUsersModal, {
    props: { show: false, caseId: 9, caseData: { users: [] } },
    attachTo: document.body,
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'VSelect' }).props('items')).toEqual([])
  const strixySwitch = wrapper.findComponent({ name: 'VSwitch' })
  expect(strixySwitch.props('modelValue')).toBe(false)
  strixySwitch.vm.$emit('update:modelValue', true)
  await flushPromises()
  expect(caseService.addUserToCase).toHaveBeenCalledWith(9, 2, false)
  await wrapper.setProps({ caseData: { users: [strixy] } })
  expect(wrapper.findComponent({ name: 'VSwitch' }).props('modelValue')).toBe(true)
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).not.toContain('strixy_ai_1')
  const confirm = vi.spyOn(window, 'confirm')
  wrapper.findComponent({ name: 'VSwitch' }).vm.$emit('update:modelValue', false)
  await flushPromises()
  expect(caseService.removeUserFromCase).toHaveBeenCalledWith(9, 2)
  expect(confirm).not.toHaveBeenCalled()
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
        detail: 'Strixy is not enabled on this case. Ask an administrator to enable it.',
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
  expect(wrapper.text()).toContain('Strixy is not enabled on this case')
  expect(wrapper.get('[aria-label="Message input"]').element.disabled).toBe(true)
  strixyService.getAvailability.mockResolvedValueOnce({ is_configured: true })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Check again')
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('Strixy is not enabled')
  expect(wrapper.get('[aria-label="Message input"]').element.disabled).toBe(false)
})
