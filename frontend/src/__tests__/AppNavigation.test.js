import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from '../components/__tests__/helpers/vuetify'
import App from '../App.vue'
import { createAppRouter } from '../router'
import { useAuthStore } from '../stores/auth'
import { useActiveCaseStore } from '../stores/activeCase'
import { caseService } from '../services/case'
import { clientService } from '../services/client'

vi.mock('../services/case', () => ({ caseService: { getCases: vi.fn() } }))
vi.mock('../services/client', () => ({ clientService: { getClients: vi.fn() } }))
vi.mock('../services/auth', () => ({
  authService: {
    isAuthenticated: () => false,
    getSetupStatus: async () => ({ setup_required: false }),
    logout: vi.fn(),
  },
}))
vi.mock('../services/system', () => ({
  systemService: { checkApiKeyStatus: async () => ({ is_configured: true }) },
}))
vi.mock('../composables/useDarkMode', async () => {
  const { ref } = await import('vue')
  return { useDarkMode: () => ({ isDark: ref(false), toggleDark: vi.fn() }) }
})

let pinia
const cases = [
  { id: 1, case_number: 'ONE', title: 'First case', status: 'Open' },
  { id: 2, case_number: 'TWO', title: 'Second case', status: 'Open' },
]

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  pinia = createPinia()
  setActivePinia(pinia)
  Object.assign(useAuthStore(), {
    isInitialized: true,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin' },
  })
  caseService.getCases.mockResolvedValue([])
  clientService.getClients.mockResolvedValue([])
})

it('keeps one sidebar across Settings, Strixy, and case switches while resetting page state', async () => {
  caseService.getCases.mockResolvedValue(cases)
  const { wrapper, router } = await openApp()
  const sidebar = wrapper.get('.owlculus-sidebar').element
  const logo = wrapper.get('[aria-label="Owlculus Logo"]').element

  for (const path of ['/settings', '/case/1/strixy', '/case/2/strixy', '/clients']) {
    await router.push(path)
    await flushPromises()
    expect(wrapper.findAll('.owlculus-sidebar')).toHaveLength(1)
    expect(wrapper.get('.owlculus-sidebar').element).toBe(sidebar)
    expect(wrapper.get('[aria-label="Owlculus Logo"]').element).toBe(logo)

    if (path === '/case/1/strixy') {
      await wrapper.get('input[aria-label="Message input"]').setValue('First case draft')
    }
    if (path === '/case/2/strixy') {
      expect(wrapper.get('input[aria-label="Message input"]').element.value).toBe('')
      expect(wrapper.text()).toContain('Strixy · TWO')
    }
  }
})

it('retains the sidebar while case access fails and recovers', async () => {
  caseService.getCases.mockResolvedValue(cases)
  const { wrapper } = await openApp('/case/1/strixy')
  const sidebar = wrapper.get('.owlculus-sidebar').element
  const activeCase = useActiveCaseStore()

  caseService.getCases.mockRejectedValueOnce(new Error('Unavailable'))
  await activeCase.initialize(1)
  await flushPromises()
  expect(wrapper.text()).toContain('Unable to load accessible cases')
  expect(wrapper.find('input[aria-label="Message input"]').exists()).toBe(false)
  expect(wrapper.findAll('.owlculus-sidebar')).toHaveLength(1)
  expect(wrapper.get('.owlculus-sidebar').element).toBe(sidebar)

  await activeCase.refresh()
  await flushPromises()
  expect(wrapper.find('input[aria-label="Message input"]').exists()).toBe(true)
  expect(wrapper.get('.owlculus-sidebar').element).toBe(sidebar)
})

it.each(['/login', '/register', '/setup'])(
  'hides the sidebar on the public %s page',
  async (path) => {
    Object.assign(useAuthStore(), {
      isAuthenticated: false,
      user: null,
      setupRequired: path === '/setup',
    })
    const { wrapper, router } = await openApp(path)
    expect(router.currentRoute.value.path).toBe(path)
    expect(wrapper.find('.owlculus-sidebar').exists()).toBe(false)
  },
)

it('removes the sidebar when the user logs out', async () => {
  const { wrapper, router } = await openApp()
  await wrapper.get('button[aria-label="Logout"]').trigger('click')
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/login'))
  await flushPromises()
  expect(wrapper.find('.owlculus-sidebar').exists()).toBe(false)
})

async function openApp(path = '/cases') {
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mountWithVuetify(App, {
    global: {
      plugins: [pinia, router],
      stubs: { NewCaseModal: true, NewClientModal: true, EditClientModal: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

it('keeps the sidebar and logo mounted when navigating from Cases to Clients and back', async () => {
  const { wrapper, router } = await openApp()
  const sidebar = wrapper.get('.owlculus-sidebar').element
  const logo = wrapper.get('[aria-label="Owlculus Logo"]').element

  for (const path of ['/clients', '/cases']) {
    await wrapper.get(`a[href="${path}"]`).trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe(path))
    await flushPromises()

    expect(wrapper.findAll('.owlculus-sidebar')).toHaveLength(1)
    expect(wrapper.get('.owlculus-sidebar').element).toBe(sidebar)
    expect(wrapper.get('[aria-label="Owlculus Logo"]').element).toBe(logo)
    expect(wrapper.get('h1').text()).toBe(path === '/clients' ? 'Clients' : 'Cases')
  }
})

it('keeps the mobile navigation rail and case switcher mounted during navigation', async () => {
  vi.stubGlobal('innerWidth', 390)
  const { wrapper, router } = await openApp()
  const sidebar = wrapper.get('.owlculus-sidebar').element
  const caseSwitcherBar = wrapper.get('.v-app-bar').element

  await wrapper.get('a[href="/clients"]').trigger('click')
  await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/clients'))
  await flushPromises()

  expect(wrapper.get('.owlculus-sidebar').element).toBe(sidebar)
  expect(wrapper.get('.v-app-bar').element).toBe(caseSwitcherBar)
  expect(wrapper.findAll('.v-app-bar')).toHaveLength(1)
})
