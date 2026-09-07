import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import Settings from '../Settings.vue'
import Login from '../Login.vue'
import { useAuthStore } from '../../stores/auth'

const replace = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ replace }),
  useRoute: () => ({ query: { passwordChanged: '1' } }),
}))
vi.mock('../../services/auth')
vi.mock('../../composables/useDarkMode', () => ({ useDarkMode: () => ({ isDark: false }) }))
const layout = defineComponent({ template: '<div><slot /></div>' })
const stubs = Object.fromEntries(
  ['VMain', 'VContainer', 'VRow', 'VCol', 'VCard', 'VCardText', 'VCardTitle'].map((name) => [
    name,
    layout,
  ]),
)
stubs.VForm = defineComponent({
  emits: ['submit'],
  template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>',
})
stubs.VTextField = defineComponent({
  props: ['modelValue', 'label'],
  emits: ['update:modelValue'],
  template:
    '<input :aria-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})
stubs.VAlert = defineComponent({ props: ['text'], template: '<div role="alert">{{ text }}</div>' })
stubs.VBtn = layout
stubs.VImg = true
stubs.VIcon = true

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  vi.clearAllMocks()
})

it.each([true, false])(
  'returns to sign-in with success messaging only on a successful change: %s',
  async (succeeds) => {
    const store = useAuthStore()
    vi.spyOn(store, 'changePassword')[succeeds ? 'mockResolvedValue' : 'mockRejectedValue'](
      succeeds ? undefined : { response: { data: { detail: 'Invalid current password' } } },
    )
    const wrapper = mount(Settings, { global: { stubs } })
    await wrapper.get('[aria-label="Current Password"]').setValue('old-password')
    await wrapper.get('[aria-label="New Password"]').setValue('new-password')
    await wrapper.get('[aria-label="Confirm New Password"]').setValue('new-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    if (succeeds) {
      expect(replace).toHaveBeenCalledWith({ path: '/login', query: { passwordChanged: '1' } })
      const login = mount(Login, { global: { stubs } })
      expect(login.get('[role="alert"]').text()).toBe(
        'Password changed successfully. Sign in with your new password.',
      )
    } else {
      expect(replace).not.toHaveBeenCalled()
      expect(wrapper.get('[role="alert"]').text()).toBe('Invalid current password')
    }
  },
)
