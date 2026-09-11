import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authService } from '../../services/auth'
import { useAuthStore } from '../../stores/auth'
import Setup from '../Setup.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../composables/useDarkMode', () => ({
  useDarkMode: () => ({ isDark: { value: false } }),
}))

vi.mock('../../services/auth')

const LayoutStub = defineComponent({ template: '<div><slot /></div>' })
const FormStub = defineComponent({
  emits: ['submit'],
  template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>',
})
const TextFieldStub = defineComponent({
  props: {
    modelValue: { type: String, default: '' },
    label: { type: String, required: true },
    type: { type: String, default: 'text' },
    placeholder: { type: String, default: undefined },
    autocomplete: { type: String, default: undefined },
    disabled: Boolean,
    autofocus: Boolean,
  },
  emits: ['update:modelValue'],
  template: `
    <input
      :aria-label="label"
      :value="modelValue"
      :type="type"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :disabled="disabled"
      :autofocus="autofocus"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  `,
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, type: { type: String, default: 'button' } },
  template: '<button :disabled="disabled" :type="type"><slot /></button>',
})
const AlertStub = defineComponent({ template: '<div role="alert"><slot /></div>' })

const mountSetup = () =>
  mount(Setup, {
    global: {
      stubs: {
        VMain: LayoutStub,
        VContainer: LayoutStub,
        VRow: LayoutStub,
        VCol: LayoutStub,
        VCard: LayoutStub,
        VCardText: LayoutStub,
        VImg: defineComponent({ template: '<img />' }),
        VForm: FormStub,
        VTextField: TextFieldStub,
        VBtn: ButtonStub,
        VAlert: AlertStub,
      },
    },
  })

const fillValidForm = async (wrapper) => {
  await wrapper.get('[aria-label="Setup Token"]').setValue('server-token')
  await wrapper.get('[aria-label="Username"]').setValue('owl_admin')
  await wrapper.get('[aria-label="Email"]').setValue('admin@example.com')
  await wrapper.get('[aria-label="Password"]').setValue('long-password')
  await wrapper.get('[aria-label="Confirm Password"]').setValue('long-password')
}

describe('setup page', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders the administrator form in the required order with setup token guidance', () => {
    const wrapper = mountSetup()
    const fields = wrapper.findAll('input')

    expect(wrapper.text()).toContain('Welcome to Owlculus')
    expect(wrapper.text()).toContain('Create your administrator account to get started')
    expect(fields.map((field) => field.attributes('aria-label'))).toEqual([
      'Setup Token',
      'Username',
      'Email',
      'Password',
      'Confirm Password',
    ])
    expect(fields[0].attributes('placeholder')).toBe('Find this in the server console output.')
    expect(fields[0].attributes()).toHaveProperty('autofocus')
    expect(fields[1].attributes('autocomplete')).toBe('username')
    expect(fields[2].attributes('autocomplete')).toBe('email')
    expect(fields[3].attributes('autocomplete')).toBe('new-password')
    expect(fields[4].attributes('autocomplete')).toBe('new-password')
    expect(wrapper.get('button').text()).toBe('Create Administrator Account')
  })

  it.each([
    [
      'different password confirmation',
      'long-password',
      'different-password',
      'Passwords do not match',
    ],
    ['a short password', 'short', 'short', 'Password must be at least 10 characters'],
  ])('rejects %s before making a request', async (_, password, confirmation, expectedError) => {
    const wrapper = mountSetup()
    await fillValidForm(wrapper)
    await wrapper.get('[aria-label="Password"]').setValue(password)
    await wrapper.get('[aria-label="Confirm Password"]').setValue(confirmation)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[role="alert"]').text()).toBe(expectedError)
    expect(authService.createAdministrator).not.toHaveBeenCalled()
  })

  it.each([
    ['ab', 'admin@example.com', 'Username must be between 3 and 50 characters'],
    [
      'admin-user',
      'admin@example.com',
      'Username can only contain letters, numbers, and underscores',
    ],
    ['owl_admin', 'not-an-email', 'Please enter a valid email address'],
    ['owl_admin', 'admin@owlculus.local', 'Please enter a valid email address'],
  ])('validates username and email before submitting', async (username, email, expectedError) => {
    const wrapper = mountSetup()
    await fillValidForm(wrapper)
    await wrapper.get('[aria-label="Username"]').setValue(username)
    await wrapper.get('[aria-label="Email"]').setValue(email)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[role="alert"]').text()).toBe(expectedError)
    expect(authService.createAdministrator).not.toHaveBeenCalled()
  })

  it('keeps values and re-enables the form after a backend error', async () => {
    authService.createAdministrator.mockRejectedValue({
      response: { data: { detail: 'Invalid setup token' } },
    })
    const wrapper = mountSetup()
    await fillValidForm(wrapper)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Invalid setup token')
    expect(wrapper.get('[aria-label="Username"]').element.value).toBe('owl_admin')
    expect(wrapper.findAll('input').every((field) => !field.element.disabled)).toBe(true)
    expect(wrapper.get('button').element.disabled).toBe(false)
  })

  it('disables every control while creating the administrator and then navigates to login', async () => {
    let resolveRequest
    authService.createAdministrator.mockImplementation(
      () => new Promise((resolve) => (resolveRequest = resolve)),
    )
    const wrapper = mountSetup()
    const store = useAuthStore()
    store.setupRequired = true
    await fillValidForm(wrapper)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('input').every((field) => field.element.disabled)).toBe(true)
    expect(wrapper.get('button').element.disabled).toBe(true)
    expect(wrapper.get('button').text()).toBe('Creating account...')

    resolveRequest({ id: 1 })
    await flushPromises()

    expect(authService.createAdministrator).toHaveBeenCalledWith({
      setup_token: 'server-token',
      username: 'owl_admin',
      email: 'admin@example.com',
      password: 'long-password',
    })
    expect(store.setupRequired).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(push).toHaveBeenCalledWith('/login')
  })
})
