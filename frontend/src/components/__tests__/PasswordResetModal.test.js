import { expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import PasswordResetModal from '../PasswordResetModal.vue'
import { userService } from '@/services/user'

vi.mock('@/services/user', () => ({ userService: { resetPassword: vi.fn() } }))

it('blocks weak or mismatched passwords and resets with a valid one', async () => {
  const wrapper = mountWithVuetify(PasswordResetModal, {
    props: { show: false, userId: 4 },
    attachTo: document.body,
  })
  await wrapper.setProps({ show: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  const [password, confirmation] = dialog.findAll('input')
  const submit = dialog.findAll('button').find((button) => button.text() === 'Reset Password')

  await password.setValue('letters-only')
  await confirmation.setValue('letters-only')
  expect(dialog.text()).toContain('Password must contain at least one number')
  expect(submit.element.disabled).toBe(true)

  await password.setValue('Str0ng!password')
  await confirmation.setValue('Str0ng!password')
  await flushPromises()
  expect(dialog.text()).toContain('Strong')
  expect(submit.element.disabled).toBe(false)

  // Changing the password after confirming must not slip past the match rule.
  await password.setValue('Other-passw0rd')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(userService.resetPassword).not.toHaveBeenCalled()
  expect(dialog.text()).toContain('Passwords do not match')

  await confirmation.setValue('Other-passw0rd')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(userService.resetPassword).toHaveBeenCalledWith(4, 'Other-passw0rd')
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})
