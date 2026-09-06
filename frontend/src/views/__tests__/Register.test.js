import { AxiosError } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mountWithVuetify } from '../../components/__tests__/helpers/vuetify'
import api from '../../services/api'
import { useAuthStore } from '../../stores/auth'
import Register from '../Register.vue'

// Color scheme is unrelated to invite validation and account creation.
vi.mock('../../composables/useDarkMode', () => ({
  useDarkMode: () => ({ isDark: false }),
}))

const originalAdapter = api.defaults.adapter
const details = {
  Username: 'invited_owl',
  'Email Address': 'invited@example.com',
  Password: 'long-password',
  'Confirm Password': 'long-password',
}
let requests
let validation
let registration
let pinia

function deferred() {
  let resolve
  const promise = new Promise((done) => (resolve = done))
  return { promise, resolve }
}

function response(config, data, status = 200) {
  const result = { config, data, status, statusText: String(status), headers: {} }
  if (status >= 400)
    throw new AxiosError('Request failed', 'ERR_BAD_RESPONSE', config, null, result)
  return result
}

function field(wrapper, name) {
  const label = wrapper
    .findAll('label')
    .find((label) => label.text() === name && label.attributes('for'))
  return wrapper.get(`input[id="${label.attributes('for')}"]`)
}

function button(wrapper, name) {
  return wrapper.findAll('button').find((button) => button.text().trim() === name)
}

function writes() {
  return requests.filter((request) => request.url === '/api/invites/register')
}

async function openRegistration(token = 'invite-token') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/register', component: Register },
      { path: '/login', component: { template: '<p>Login</p>' } },
    ],
  })
  await router.push({ path: '/register', query: token ? { token } : {} })
  await router.isReady()
  const wrapper = mountWithVuetify(
    { template: '<v-app><router-view /></v-app>' },
    {
      attachTo: document.body,
      global: { plugins: [pinia, router] },
    },
  )
  await flushPromises()
  return { wrapper, router }
}

async function fillForm(wrapper, overrides = {}) {
  for (const [name, value] of Object.entries({ ...details, ...overrides })) {
    await field(wrapper, name).setValue(value)
  }
}

// jsdom does not implement Enter's implicit form submission. Dispatch the native
// public submit event it produces; keep the real VForm and its validation intact.
async function submitWithKeyboard(wrapper) {
  await field(wrapper, 'Confirm Password').trigger('keydown', { key: 'Enter' })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

describe('invite registration workflow', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    localStorage.clear()
    sessionStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
    requests = []
    validation = (config) =>
      response(config, {
        valid: true,
        role: 'Investigator',
        expires_at: '2026-09-13T00:00:00Z',
        error: null,
      })
    registration = (config) =>
      response(config, {
        id: 42,
        username: details.Username,
        email: details['Email Address'],
        role: 'Investigator',
        created_at: '2026-09-06T00:00:00Z',
      })
    api.defaults.adapter = async (config) => {
      requests.push({ url: config.url, method: config.method, data: JSON.parse(config.data) })
      if (config.url === '/api/invites/validate') return validation(config)
      if (config.url === '/api/invites/register') return registration(config)
      throw new Error(`Unexpected request: ${config.method} ${config.url}`)
    }
  })

  afterEach(() => {
    api.defaults.adapter = originalAdapter
    vi.clearAllTimers()
    vi.useRealTimers()
    localStorage.clear()
    sessionStorage.clear()
  })

  it.each([
    ['Admin', 'Full system access and user management'],
    ['Investigator', 'Read/write access, can run plugins'],
    ['Analyst', 'Read-only access to assigned cases'],
  ])(
    'validates the public route token and displays the %s account role',
    async (role, description) => {
      validation = (config) =>
        response(config, { valid: true, role, expires_at: null, error: null })
      const { wrapper } = await openRegistration('token-with+reserved/chars')

      expect(requests).toEqual([
        {
          url: '/api/invites/validate',
          method: 'post',
          data: { token: 'token-with+reserved/chars' },
        },
      ])
      expect(wrapper.text()).toContain(`You're registering as a ${role}`)
      expect(wrapper.text()).toContain(description)
      expect(wrapper.findAll('input')).toHaveLength(4)
      expect(button(wrapper, 'Create Account').element.disabled).toBe(true)
    },
  )

  it('keeps the form unavailable while token validation is pending', async () => {
    const pending = deferred()
    validation = async (config) => response(config, await pending.promise)
    const { wrapper } = await openRegistration()

    expect(wrapper.text()).toContain('Validating invite...')
    expect(wrapper.find('form').exists()).toBe(false)
    pending.resolve({ valid: true, role: 'Analyst', expires_at: null, error: null })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Validating invite...')
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('explains a missing token without requesting validation and returns to login', async () => {
    const { wrapper, router } = await openRegistration(null)
    expect(
      wrapper
        .findAll('[role="alert"]')
        .map((alert) => alert.text())
        .join(' '),
    ).toContain('No invite token provided')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(requests).toEqual([])
    await button(wrapper, 'Back to Login').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it.each(['Invalid invite token', 'Invite has expired', 'Invite has already been used'])(
    'renders the backend invalid-invite response: %s',
    async (error) => {
      validation = (config) =>
        response(config, { valid: false, role: null, expires_at: null, error })
      const { wrapper } = await openRegistration()
      expect(
        wrapper
          .findAll('[role="alert"]')
          .map((alert) => alert.text())
          .join(' '),
      ).toContain(error)
      expect(wrapper.text()).not.toContain('Validating invite...')
      expect(wrapper.find('form').exists()).toBe(false)
      expect(writes()).toEqual([])
    },
  )

  it.each([
    [
      { detail: 'Invite validation temporarily unavailable' },
      'Invite validation temporarily unavailable',
    ],
    [{}, 'Failed to validate invite token'],
  ])('finishes token loading and explains HTTP validation failure', async (body, message) => {
    validation = (config) => response(config, body, 503)
    const { wrapper } = await openRegistration()
    expect(
      wrapper
        .findAll('[role="alert"]')
        .map((alert) => alert.text())
        .join(' '),
    ).toContain(message)
    expect(wrapper.text()).not.toContain('Validating invite...')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  const invalidDetails = [
    ['missing username', { Username: '' }],
    ['short username', { Username: 'ab' }],
    ['missing email', { 'Email Address': '' }],
    ['invalid email', { 'Email Address': 'not-an-email' }],
    ['missing password', { Password: '', 'Confirm Password': '' }],
    ['short password', { Password: 'short', 'Confirm Password': 'short' }],
    ['missing confirmation', { 'Confirm Password': '' }],
    ['mismatched passwords', { 'Confirm Password': 'different-password' }],
  ]

  it.each(invalidDetails)('blocks button submission for %s', async (_, overrides) => {
    const { wrapper } = await openRegistration()
    await fillForm(wrapper, overrides)
    const submit = button(wrapper, 'Create Account')
    expect(submit.element.disabled).toBe(true)
    submit.element.click()
    await flushPromises()
    expect(writes()).toEqual([])
  })

  // Known defect: .scratch/frontend-test-coverage-defects/issues/02-registration-validation.md
  it.fails.each(invalidDetails)(
    'rejects %s through keyboard form submission',
    async (_, overrides) => {
      const { wrapper } = await openRegistration()
      await fillForm(wrapper, overrides)
      await submitWithKeyboard(wrapper)
      expect(writes()).toEqual([])
      expect(wrapper.text()).not.toContain('Registration Successful!')
    },
  )

  it.each(['button', 'keyboard'])(
    'registers valid details through %s and redirects after confirmation',
    async (action) => {
      const { wrapper, router } = await openRegistration()
      const auth = useAuthStore()
      await fillForm(wrapper)
      if (action === 'button') {
        button(wrapper, 'Create Account').element.click()
        await flushPromises()
      } else {
        await submitWithKeyboard(wrapper)
      }

      expect(writes()).toEqual([
        {
          url: '/api/invites/register',
          method: 'post',
          data: {
            username: 'invited_owl',
            email: 'invited@example.com',
            password: 'long-password',
            token: 'invite-token',
          },
        },
      ])
      expect(
        wrapper
          .findAll('[role="alert"]')
          .map((alert) => alert.text())
          .join(' '),
      ).toContain('Registration Successful!')
      expect(auth.isAuthenticated).toBe(false)
      expect(auth.user).toBeNull()
      expect(localStorage.getItem('access_token')).toBeNull()
      expect(localStorage.getItem('token_type')).toBeNull()
      await vi.advanceTimersByTimeAsync(1999)
      expect(router.currentRoute.value.path).toBe('/register')
      await vi.advanceTimersByTimeAsync(1)
      await flushPromises()
      expect(router.currentRoute.value.path).toBe('/login')
      expect(auth.isAuthenticated).toBe(false)
    },
  )

  it('disables controls and ignores repeated button clicks while registration is pending', async () => {
    const pending = deferred()
    registration = async (config) => response(config, await pending.promise)
    const { wrapper } = await openRegistration()
    await fillForm(wrapper)
    button(wrapper, 'Create Account').element.click()
    await flushPromises()

    expect(wrapper.findAll('input').every((input) => input.element.disabled)).toBe(true)
    expect(button(wrapper, 'Back to Login').element.disabled).toBe(true)
    const submit = button(wrapper, 'Creating Account...')
    expect(submit.element.disabled).toBe(true)
    submit.element.click()
    await flushPromises()
    expect(writes()).toHaveLength(1)
    expect(wrapper.text()).not.toContain('Registration Successful!')
    pending.resolve({ id: 42 })
    await flushPromises()
  })

  it.each([
    [{ detail: 'Username already exists' }, 'Username already exists'],
    [{}, 'Failed to create account. Please try again.'],
  ])(
    'retains entered details after registration failure and allows retry',
    async (body, message) => {
      registration = (config) => response(config, body, 409)
      const { wrapper, router } = await openRegistration()
      await fillForm(wrapper)
      button(wrapper, 'Create Account').element.click()
      await flushPromises()

      expect(
        wrapper
          .findAll('[role="alert"]')
          .map((alert) => alert.text())
          .join(' '),
      ).toContain(message)
      expect(wrapper.text()).not.toContain('Registration Successful!')
      expect(router.currentRoute.value.path).toBe('/register')
      for (const [name, value] of Object.entries(details)) {
        expect(field(wrapper, name).element.value).toBe(value)
        expect(field(wrapper, name).element.disabled).toBe(false)
      }
      expect(button(wrapper, 'Create Account').element.disabled).toBe(false)
      registration = (config) => response(config, { id: 42 })
      button(wrapper, 'Create Account').element.click()
      await flushPromises()

      expect(writes()).toHaveLength(2)
      expect(writes()[1]).toEqual(writes()[0])
      expect(
        wrapper
          .findAll('[role="alert"]')
          .map((alert) => alert.text())
          .join(' '),
      ).toContain('Registration Successful!')
      expect(wrapper.text()).not.toContain(message)
    },
  )
})
