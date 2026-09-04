import { expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import UserModal from '../UserModal.vue'
import { userService } from '@/services/user'

vi.mock('@/services/user', () => ({ userService: { createUser: vi.fn() } }))
let wrapper
it('blocks invalid keyboard submissions and saves a valid new user', async () => {
  wrapper = mountWithVuetify(UserModal, {
    props: { show: false },
    attachTo: document.body,
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  const submit = dialog.findAll('button').find((button) => button.text() === 'Create User')
  expect(submit.element.form).toBe(dialog.get('form').element)
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(userService.createUser).not.toHaveBeenCalled()
  expect(dialog.text()).toContain('Username is required')
  const inputs = dialog.findAll('input')
  await inputs[0].setValue('investigator')
  await inputs[1].setValue('investigator@example.org')
  await inputs[2].setValue('StrongPassword42!')
  userService.createUser.mockResolvedValue({ id: 9 })
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(userService.createUser).toHaveBeenCalledWith({
    username: 'investigator',
    email: 'investigator@example.org',
    password: 'StrongPassword42!',
    role: 'Analyst',
    is_active: true,
  })
  expect(wrapper.emitted('saved')).toEqual([[{ id: 9 }]])
})
