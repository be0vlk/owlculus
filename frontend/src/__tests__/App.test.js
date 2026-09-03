import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App.vue'
import { authService } from '../services/auth'

vi.mock('../composables/useDarkMode', () => ({
  useDarkMode: vi.fn(),
}))

vi.mock('../services/auth', () => ({
  authService: {
    getSetupStatus: vi.fn(),
    getCurrentUser: vi.fn(),
    isAuthenticated: vi.fn(() => false),
    logout: vi.fn(),
    login: vi.fn(),
  },
}))

const LayoutStub = defineComponent({ template: '<div><slot /><slot name="actions" /></div>' })

describe('application authentication loading state', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
    authService.isAuthenticated.mockReturnValue(false)
  })

  it('shows the shared full-page loader instead of route content until setup status resolves', async () => {
    let resolveStatus
    authService.getSetupStatus.mockImplementation(
      () => new Promise((resolve) => (resolveStatus = resolve)),
    )
    const wrapper = mount(App, {
      global: {
        stubs: {
          VApp: LayoutStub,
          VSnackbar: LayoutStub,
          VBtn: LayoutStub,
          RouterView: defineComponent({ template: '<main data-testid="route-content">Login</main>' }),
          FullPageLoading: defineComponent({ template: '<main data-testid="full-page-loading" />' }),
        },
      },
    })

    expect(wrapper.find('[data-testid="full-page-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="route-content"]').exists()).toBe(false)

    resolveStatus({ setup_required: false })
    await flushPromises()
    await nextTick()

    expect(wrapper.find('[data-testid="full-page-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="route-content"]').exists()).toBe(true)
  })
})
