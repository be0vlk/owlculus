import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

// The singleton owns the production unauthorized listener; give it browser-free history.
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, createWebHistory: actual.createMemoryHistory }
})
vi.mock('../../composables/useDarkMode', () => ({ useDarkMode: vi.fn() }))

let api
let axios
let originalAdapter
let auth
let activeCase
let router
let wrapper
let transport
let events
let listeners
let push
let pinia

function response(config, data) {
  return { config, data, status: 200, statusText: 'OK', headers: {} }
}

function rejectRequest(config, status) {
  const response = { config, data: { detail: 'Request rejected' }, status, headers: {} }
  return Promise.reject(
    new axios.AxiosError('Request rejected', 'ERR_BAD_RESPONSE', config, null, response),
  )
}

beforeEach(async () => {
  vi.resetModules()
  vi.stubGlobal('visualViewport', new EventTarget())
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  localStorage.clear()
  sessionStorage.clear()
  listeners = []
  const addEventListener = window.addEventListener.bind(window)
  vi.spyOn(window, 'addEventListener').mockImplementation((type, listener, options) => {
    if (type.startsWith('api:')) listeners.push([type, listener, options])
    addEventListener(type, listener, options)
  })
  axios = (await import('axios')).default
  originalAdapter = axios.defaults.adapter
  transport = vi.fn(async (config) => {
    if (config.url === '/api/auth/setup-status') return response(config, { setup_required: false })
    if (config.url === '/api/users/me') return response(config, { id: 7, role: 'Investigator' })
    if (config.url === '/api/cases/') return response(config, [{ id: 1, case_number: 'ONE' }])
    if (config.url === '/api/auth/login')
      return response(config, { access_token: 'second-session', token_type: 'Bearer' })
    throw new Error(`Unexpected request: ${config.url}`)
  })
  axios.defaults.adapter = transport
  const { createPinia, setActivePinia } = await import('pinia')
  pinia = createPinia()
  setActivePinia(pinia)
  api = (await import('../api')).default
  const routerModule = await import('../../router')
  router = routerModule.default
  for (const route of routerModule.routes) {
    if (route.name) router.removeRoute(route.name)
    router.addRoute({
      ...route,
      component: route.component ? { template: `<main>${route.name}</main>` } : undefined,
    })
  }
  localStorage.setItem('access_token', 'first-session')
  localStorage.setItem('token_type', 'Bearer')
  auth = (await import('../../stores/auth')).useAuthStore()
  activeCase = (await import('../../stores/activeCase')).useActiveCaseStore()
  await router.push('/case/1')
  const { default: App } = await import('../../App.vue')
  // Import Vuetify after module isolation so its injection symbols match App's controls.
  const { createVuetify } = await import('vuetify')
  const components = await import('vuetify/components')
  const directives = await import('vuetify/directives')
  wrapper = mount(App, {
    attachTo: document.body,
    global: {
      plugins: [pinia, router, createVuetify({ components, directives, theme: false })],
      stubs: { BaseDashboard: true },
    },
  })
  await flushPromises()
  events = vi.fn()
  window.addEventListener('api:sessionExpired', events)
  push = vi.spyOn(router, 'push')
  transport.mockClear()
})

afterEach(() => {
  wrapper?.unmount()
  for (const [type, listener, options] of listeners)
    window.removeEventListener(type, listener, options)
  router?.options.history.destroy()
  axios.defaults.adapter = originalAdapter
  pinia?._s.forEach((store) => store.$dispose())
  vi.clearAllTimers()
  vi.useRealTimers()
  localStorage.clear()
  sessionStorage.clear()
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function expireSession(count = 1) {
  api.defaults.adapter = (config) => rejectRequest(config, 401)
  const outcomes = await Promise.allSettled(
    Array.from({ length: count }, () => api.get('/api/protected')),
  )
  expect(
    outcomes.every(
      (outcome) => outcome.status === 'rejected' && outcome.reason.response.status === 401,
    ),
  ).toBe(true)
  await flushPromises()
}

function expectLoggedOut() {
  expect(localStorage.getItem('access_token')).toBeNull()
  expect(localStorage.getItem('token_type')).toBeNull()
  expect(auth.isAuthenticated).toBe(false)
  expect(auth.user).toBeNull()
  expect(activeCase.activeCaseId).toBeNull()
  expect(activeCase.accessibleCases).toEqual([])
  expect(activeCase.initialized).toBe(false)
  expect(router.currentRoute.value.path).toBe('/login')
  expect(document.body.querySelectorAll('.v-snackbar--active')).toHaveLength(1)
  expect(document.body.textContent).toContain('Your session has expired. Please log in again.')
}

describe('real authenticated transport and application session lifecycle', () => {
  it('reads the latest token and token type for every request, including the default type and absent token', async () => {
    api.defaults.adapter = vi.fn(async (config) => response(config, { ok: true }))
    await api.get('/api/protected')
    localStorage.setItem('access_token', 'rotated-session')
    localStorage.setItem('token_type', 'Token')
    await api.get('/api/protected')
    localStorage.removeItem('token_type')
    await api.get('/api/protected')
    localStorage.removeItem('access_token')
    await api.get('/api/protected')

    expect(
      api.defaults.adapter.mock.calls.map(([config]) => config.headers.get('Authorization')),
    ).toEqual([
      'Bearer first-session',
      'Token rotated-session',
      'bearer rotated-session',
      undefined,
    ])
  })

  it('clears authentication and Case authorization, shows feedback, and navigates from a protected route on HTTP 401', async () => {
    expect(auth.user.role).toBe('Investigator')
    expect(activeCase.activeCaseId).toBe(1)
    await expireSession()

    expectLoggedOut()
    expect(events).toHaveBeenCalledOnce()
    expect(push).toHaveBeenCalledExactlyOnceWith('/login')
    expect(document.body.querySelector('main').textContent).toBe('Login')
  })

  it('coalesces concurrent unauthorized navigation and handles a later independently expired session', async () => {
    await expireSession(3)
    expectLoggedOut()
    expect(push).toHaveBeenCalledExactlyOnceWith('/login')
    expect(document.body.querySelectorAll('.v-snackbar--active')).toHaveLength(1)
    const close = [...document.body.querySelectorAll('button')].find(
      (button) => button.textContent.trim() === 'Close',
    )
    close.click()
    await flushPromises()
    expect(document.body.querySelectorAll('.v-snackbar--active')).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(101)

    api.defaults.adapter = transport
    await auth.login('investigator', 'password')
    await router.push('/case/1')
    expect(activeCase.activeCaseId).toBe(1)
    push.mockClear()
    events.mockClear()
    await expireSession()

    expectLoggedOut()
    expect(push).toHaveBeenCalledExactlyOnceWith('/login')
    expect(events).toHaveBeenCalledOnce()
  })

  it.each([403, 500])(
    'preserves the authenticated session and distinct rejection on HTTP %s',
    async (status) => {
      api.defaults.adapter = (config) => rejectRequest(config, status)
      await expect(api.get('/api/protected')).rejects.toMatchObject({
        response: { status, data: { detail: 'Request rejected' } },
      })
      await flushPromises()

      expect(auth.isAuthenticated).toBe(true)
      expect(auth.user.id).toBe(7)
      expect(activeCase.activeCaseId).toBe(1)
      expect(activeCase.accessibleCases).toEqual([{ id: 1, case_number: 'ONE' }])
      expect(localStorage.getItem('access_token')).toBe('first-session')
      expect(localStorage.getItem('token_type')).toBe('Bearer')
      expect(router.currentRoute.value.path).toBe('/case/1')
      expect(events).not.toHaveBeenCalled()
      expect(push).not.toHaveBeenCalled()
      expect(document.body.textContent).not.toContain('Your session has expired')
    },
  )
})
