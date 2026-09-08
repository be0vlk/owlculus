import { defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mountWithVuetify } from '@/components/__tests__/helpers/vuetify'
import { createAppRouter } from '@/router'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

let router, originalAdapter, adapter, users, invites
const response = (config, data) => ({ config, data, status: 200, statusText: 'OK', headers: {} })
const reject = () =>
  Promise.reject({ response: { status: 500, data: { detail: 'Service unavailable' } } })
const user = (id, username, role) => ({
  id,
  username,
  role,
  email: `${username}@example.test`,
  created_at: '2026-01-01T00:00:00Z',
})
const invite = (id, role, extra = {}) => ({
  id,
  role,
  is_used: false,
  is_expired: false,
  created_at: '2026-01-01T00:00:00Z',
  expires_at: '2027-01-01T00:00:00Z',
  ...extra,
})
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setActivePinia(createPinia())
  Object.assign(useAuthStore(), {
    isInitialized: true,
    setupRequired: false,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin', is_superadmin: true },
  })
  localStorage.setItem('access_token', 'test-session')
  vi.spyOn(console, 'error').mockImplementation(() => {})
  users = [user(1, 'Ada', 'Admin'), user(2, 'Ben', 'Investigator'), user(3, 'Cleo', 'Analyst')]
  invites = [
    invite(1, 'Admin'),
    invite(2, 'Investigator', { is_expired: true }),
    invite(3, 'Analyst', { is_used: true }),
  ]
  originalAdapter = api.defaults.adapter
  adapter = vi.fn(async (config) => {
    if (config.url === '/api/users/') return response(config, users)
    if (config.url === '/api/invites/') return response(config, invites)
    if (config.url === '/api/admin/configuration')
      return response(config, { case_number_template: 'PREFIX-YYMM-NN', case_number_prefix: 'OWL' })
    if (config.url.startsWith('/api/admin/configuration/preview?'))
      return response(config, { example_case_number: 'OWL-2609-01' })
    if (config.url === '/api/admin/configuration/api-keys') return response(config, {})
    if (config.url === '/api/admin/configuration/evidence-templates')
      return response(config, {
        templates: {
          Person: {
            name: 'Person',
            folders: [{ name: 'Background', description: 'Keep me', subfolders: [] }],
          },
        },
      })
    if (config.url === '/api/tasks/templates') return response(config, [])
    throw new Error(`Unexpected request: ${config.method} ${config.url}`)
  })
  api.defaults.adapter = adapter
  router = createAppRouter(createMemoryHistory())
})
afterEach(() => {
  api.defaults.adapter = originalAdapter
  router.options.history.destroy()
  localStorage.clear()
  sessionStorage.clear()
})
async function mountDashboard(path = '/admin') {
  await router.push(path)
  await router.isReady()
  const wrapper = mountWithVuetify(
    defineComponent({ template: '<v-app><router-view /></v-app>' }),
    { attachTo: document.body, global: { plugins: [router] } },
  )
  await flushPromises()
  return wrapper
}
const button = (wrapper, name) =>
  wrapper.findAll('button').find((item) => item.isVisible() && item.text().trim() === name)
const panel = (wrapper, tab) => wrapper.get(`#admin-panel-${tab}`)
async function select(wrapper, label) {
  await button(wrapper, label).trigger('click')
  const top = {
    Users: 'users',
    Invites: 'invites',
    'API keys': 'keys',
    Templates: 'templates',
    'Case numbering': 'configuration',
    'Invite user': 'invites',
  }[label]
  if (top) await vi.waitFor(() => expect(router.currentRoute.value.query.tab).toBe(top))
  await flushPromises()
}
function input(wrapper, label) {
  const element = wrapper.findAll('label[for]').find((item) => item.text() === label)
  return wrapper.get(`#${element.attributes('for')}`)
}
async function choose(wrapper, label, option) {
  await input(wrapper, label).trigger('mousedown')
  await flushPromises()
  const item = [...document.querySelectorAll('[role="option"]')].find(
    (item) => item.textContent.trim() === option,
  )
  expect(item, `Option ${option}`).toBeTruthy()
  item.click()
  await flushPromises()
}
describe('routed Admin workspaces', () => {
  it('opens Users without an active case and navigates all areas preserving other query state', async () => {
    const wrapper = await mountDashboard('/admin?source=bookmark')
    expect(panel(wrapper, 'users').isVisible()).toBe(true)
    expect(wrapper.get('header').text()).toContain('3 users')
    expect(wrapper.get('header').text()).toContain('1 pending invites')
    for (const [label, tab] of [
      ['Invites', 'invites'],
      ['API keys', 'keys'],
      ['Templates', 'templates'],
      ['Case numbering', 'configuration'],
      ['Users', 'users'],
    ]) {
      await select(wrapper, label)
      expect(router.currentRoute.value.query).toEqual({ source: 'bookmark', tab })
      expect(
        wrapper.findAll('[id^="admin-panel-"]').filter((item) => item.isVisible()),
      ).toHaveLength(1)
      expect(panel(wrapper, tab).isVisible()).toBe(true)
    }
  })
  it.each(['invites', 'keys', 'templates', 'configuration', 'users', 'unknown'])(
    'initializes a fresh direct link to %s',
    async (tab) => {
      const wrapper = await mountDashboard(`/admin?tab=${tab}`)
      expect(panel(wrapper, tab === 'unknown' ? 'users' : tab).isVisible()).toBe(true)
    },
  )
  it('searches and filters users and retains them across workspace switches', async () => {
    const wrapper = await mountDashboard()
    await input(panel(wrapper, 'users'), 'Search users...').setValue('example.test')
    await choose(panel(wrapper, 'users'), 'Filter by role', 'Investigator')
    expect(panel(wrapper, 'users').text()).toContain('Ben@example.test')
    expect(panel(wrapper, 'users').text()).not.toContain('Ada@example.test')
    await select(wrapper, 'API keys')
    await select(wrapper, 'Users')
    expect(input(panel(wrapper, 'users'), 'Search users...').element.value).toBe('example.test')
    expect(panel(wrapper, 'users').text()).not.toContain('Cleo@example.test')
  })
  it('opens invitations from Users and separates pending, expired and used invitations', async () => {
    const wrapper = await mountDashboard()
    await select(wrapper, 'Invite user')
    expect(router.currentRoute.value.query.tab).toBe('invites')
    const dialog = new DOMWrapper(
      document.querySelector('[role="dialog"][aria-label="Generate Invite"]'),
    )
    expect(dialog.isVisible()).toBe(true)
    await button(dialog, 'Cancel').trigger('click')
    await flushPromises()
    const content = panel(wrapper, 'invites')
    expect(document.activeElement).toBe(button(content, 'Invite user').element)
    expect(content.get('tbody').text()).toContain('Pending')
    expect(content.get('tbody').text()).not.toContain('Expired')
    expect(content.get('tbody').text()).not.toContain('Used')
    await choose(content, 'Invitation status', 'Expired')
    expect(content.get('tbody').text()).toContain('Expired')
    expect(content.get('tbody').text()).not.toContain('Pending')
    await choose(content, 'Invitation status', 'All invitations')
    expect(content.get('tbody').text()).toContain('Used')
    expect(content.get('tbody').findAll('tr')).toHaveLength(3)
  })
  it('retains configuration and evidence drafts and chosen template subtab without submitting', async () => {
    const wrapper = await mountDashboard('/admin?tab=configuration')
    await input(panel(wrapper, 'configuration'), 'Prefix (2-8 letters/numbers)').setValue('DRAFT')
    await select(wrapper, 'Templates')
    const folder = wrapper.get('#template-panel-evidence input[placeholder="Folder name"]')
    await folder.setValue('Unsaved folder')
    await folder.trigger('blur')
    await select(wrapper, 'Task templates')
    await select(wrapper, 'Users')
    await select(wrapper, 'Templates')
    expect(wrapper.get('#template-panel-tasks').isVisible()).toBe(true)
    await select(wrapper, 'Evidence folders')
    expect(
      wrapper.get('#template-panel-evidence input[placeholder="Folder name"]').element.value,
    ).toBe('Unsaved folder')
    await select(wrapper, 'Case numbering')
    expect(
      input(panel(wrapper, 'configuration'), 'Prefix (2-8 letters/numbers)').element.value,
    ).toBe('DRAFT')
    expect(adapter.mock.calls.every(([config]) => config.method === 'get')).toBe(true)
  })
  it('validates, saves, and reports configuration failures through the real workspace', async () => {
    const wrapper = await mountDashboard('/admin?tab=configuration')
    const content = panel(wrapper, 'configuration')
    const prefix = input(content, 'Prefix (2-8 letters/numbers)')
    await prefix.setValue('!')
    expect(button(content, 'Save Configuration').attributes('disabled')).toBeDefined()
    await prefix.setValue('NEW')
    await flushPromises()
    let finish
    adapter.mockImplementationOnce(
      (config) =>
        new Promise((resolve) => {
          finish = () => resolve(response(config, {}))
        }),
    )
    await button(content, 'Save Configuration').trigger('click')
    await flushPromises()
    expect(adapter.mock.calls.at(-1)[0].method).toBe('put')
    expect(JSON.parse(adapter.mock.calls.at(-1)[0].data)).toEqual({
      case_number_template: 'PREFIX-YYMM-NN',
      case_number_prefix: 'NEW',
    })
    expect(prefix.attributes('disabled')).toBeDefined()
    expect(document.body.textContent).not.toContain('Configuration saved successfully!')
    finish()
    await flushPromises()
    expect(document.body.textContent).toContain('Configuration saved successfully!')
    await prefix.setValue('NEXT')
    await flushPromises()
    adapter.mockImplementationOnce(reject)
    await button(content, 'Save Configuration').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Failed to save configuration. Please try again.')
    expect(prefix.element.value).toBe('NEXT')
  })
  it('updates the summary after confirming invite deletion', async () => {
    const wrapper = await mountDashboard('/admin?tab=invites')
    await panel(wrapper, 'invites').get('button[aria-label="Delete invite"]').trigger('click')
    await flushPromises()
    expect(adapter.mock.calls.every(([config]) => config.method === 'get')).toBe(true)
    const dialog = new DOMWrapper(
      document.querySelector('[role="dialog"][aria-label="Confirm Deletion"]'),
    )
    const normal = adapter.getMockImplementation()
    adapter.mockImplementation(async (config) => {
      if (config.method === 'delete') {
        invites = invites.filter((item) => item.id !== 1)
        return response(config, {})
      }
      return normal(config)
    })
    await button(dialog, 'Delete').trigger('click')
    await flushPromises()
    expect(
      adapter.mock.calls.some(
        ([config]) => config.method === 'delete' && config.url === '/api/invites/1',
      ),
    ).toBe(true)
    expect(wrapper.get('header').text()).toContain('0 pending invites')
  })
  it.each([false, true])('preserves account protections for superadmin=%s', async (superadmin) => {
    useAuthStore().user.is_superadmin = superadmin
    users = [
      user(1, 'Self', 'Admin'),
      user(2, 'Peer', 'Admin'),
      { ...user(3, 'Root', 'Admin'), is_superadmin: true },
      user(4, 'Analyst', 'Analyst'),
    ]
    const wrapper = await mountDashboard()
    const content = panel(wrapper, 'users')
    expect(content.find('button[aria-label="Edit Root"]').exists()).toBe(superadmin)
    expect(content.find('button[aria-label="More actions for Root"]').exists()).toBe(superadmin)
    for (const [name, deletable] of [
      ['Self', false],
      ['Peer', superadmin],
      ['Analyst', true],
      ...(superadmin ? [['Root', false]] : []),
    ]) {
      const activator = content.get(`button[aria-label="More actions for ${name}"]`)
      await activator.trigger('click')
      await flushPromises()
      const menu = new DOMWrapper(document.body)
      const actions = menu.findAll('.v-overlay--active .v-list-item').map((item) => item.text())
      expect(actions).toContain(`Reset password for ${name}`)
      expect(actions.includes(`Delete ${name}`)).toBe(deletable)
      await activator.trigger('click')
      await flushPromises()
    }
  })

  it('reports failed configuration loading and retries without exposing a saveable default', async () => {
    const normal = adapter.getMockImplementation()
    adapter.mockImplementation((config) =>
      config.url === '/api/admin/configuration' ? reject() : normal(config),
    )
    const wrapper = await mountDashboard('/admin?tab=configuration')
    const content = panel(wrapper, 'configuration')
    expect(content.text()).toContain('Failed to load case numbering')
    expect(button(content, 'Save Configuration').attributes('disabled')).toBeDefined()
    adapter.mockImplementation(normal)
    await button(content, 'Retry').trigger('click')
    await flushPromises()
    expect(input(content, 'Prefix (2-8 letters/numbers)').element.value).toBe('OWL')
  })

  it('shows empty data and an unavailable summary without blocking API keys', async () => {
    users = []
    invites = []
    const wrapper = await mountDashboard()
    expect(wrapper.get('header').text()).toContain('0 users')
    expect(panel(wrapper, 'users').text()).toContain('No users')
    adapter.mockImplementationOnce(reject)
    await panel(wrapper, 'users').get('button[aria-label="Refresh user list"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('header').text()).toContain('Users unavailable')
    await select(wrapper, 'API keys')
    expect(panel(wrapper, 'keys').isVisible()).toBe(true)
    expect(panel(wrapper, 'keys').text()).toContain('No API Keys Configured')
  })
})
