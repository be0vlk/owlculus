import { afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { AxiosError } from 'axios'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useTaskStore } from '@/stores/taskStore'
import { mountWithVuetify } from './vuetify'

const originalAdapter = api.defaults.adapter
const stores = []
afterEach(() => {
  api.defaults.adapter = originalAdapter
  stores.splice(0).forEach((pinia) => pinia._s.forEach((store) => store.$dispose()))
  localStorage.clear()
  sessionStorage.clear()
})

export const taskRecord = (overrides = {}) => ({
  id: 42,
  case_id: 7,
  title: 'Review evidence',
  description: 'Read the report',
  priority: 'medium',
  status: 'not_started',
  assigned_to_id: 9,
  assigned_to: { id: 9, username: 'assignee' },
  assigned_by: { id: 1, username: 'admin' },
  template_id: 3,
  custom_fields: { source: 'Original', retained: 'Keep me' },
  created_at: '2026-01-01T00:00:00Z',
  due_date: null,
  ...overrides,
})

export function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

async function responseData(response, config) {
  const result = await response
  if (result.status >= 400) {
    throw new AxiosError('Request rejected', 'ERR_BAD_RESPONSE', config, null, {
      status: result.status,
      data: { detail: result.detail },
      config,
      headers: {},
    })
  }
  return result.data
}

export async function taskWorkflow({ user = { id: 1, role: 'Admin' }, lead = false } = {}) {
  localStorage.clear()
  const pinia = createPinia()
  stores.push(pinia)
  setActivePinia(pinia)
  useAuthStore(pinia).user = user
  const users = [
    { id: user.id, username: 'current', is_lead: lead },
    { id: 9, username: 'assignee' },
    { id: 10, username: 'new-owner' },
  ]
  const cases = [
    { id: 7, users },
    { id: 8, users },
  ]
  const records = [taskRecord(), taskRecord({ id: 43, title: 'Other task' })]
  const requests = []
  const mutations = []
  const reads = new Map()
  api.defaults.adapter = async (config) => {
    const request = {
      method: config.method,
      url: config.url,
      params: config.params,
      data: config.data ? JSON.parse(config.data) : null,
    }
    requests.push(request)
    let data
    if (config.method !== 'get') {
      const response = mutations.shift()
      if (!response) throw new Error(`Unexpected mutation ${config.method} ${config.url}`)
      data = await responseData(response, config)
    } else if (reads.get(config.url)?.length) {
      data = await responseData(reads.get(config.url).shift(), config)
    } else if (config.url === '/api/cases/') data = cases
    else if (config.url === '/api/cases/7' || config.url === '/api/cases/8')
      data = cases.find((c) => config.url.endsWith(`/${c.id}`))
    else if (config.url.endsWith('/users')) data = users
    else if (config.url === '/api/tasks/templates')
      data = [
        {
          id: 3,
          display_name: 'Review',
          definition_json: { fields: [{ name: 'source', label: 'Source', type: 'text' }] },
        },
      ]
    else if (config.url === '/api/tasks/')
      data = records.filter((t) => t.case_id === config.params.case_id)
    else if (config.url === '/api/tasks/42') data = records[0]
    else throw new Error(`Unexpected request ${config.url}`)
    return { data: structuredClone(data), status: 200, statusText: 'OK', config, headers: {} }
  }
  const context = useActiveCaseStore(pinia)
  await context.initialize(7)
  const store = useTaskStore(pinia)
  await store.loadTasks()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/case/:caseId', component: { template: '<div />' } },
      { path: '/case/:caseId/tasks/:id?', component: { template: '<div />' } },
    ],
  })
  await router.push('/case/7/tasks/42')
  const errors = []
  function mount(component, props = {}) {
    return mountWithVuetify(
      {
        components: { Subject: component },
        setup: () => ({ props }),
        template: '<v-app><Subject v-bind="props" /></v-app>',
      },
      {
        attachTo: document.body,
        global: {
          plugins: [pinia, router],
          stubs: { Sidebar: true },
          config: { errorHandler: (error) => errors.push(error) },
        },
      },
    )
  }
  return {
    pinia,
    context,
    store,
    router,
    requests,
    mutations,
    reads,
    records,
    users,
    errors,
    mount,
    writes: () => requests.filter((request) => request.method !== 'get'),
  }
}

export function dialog(name) {
  const element = [...document.querySelectorAll('[role="dialog"]')].find(
    (el) => el.getAttribute('aria-label') === name && el.getAttribute('aria-hidden') !== 'true',
  )
  if (!element) throw new Error(`Missing dialog ${name}`)
  return new DOMWrapper(element)
}
export function button(root, name) {
  const found = root
    .findAll('button')
    .find((item) => item.text().trim() === name || item.attributes('aria-label') === name)
  if (!found) throw new Error(`Missing button ${name}`)
  return found
}
export function field(root, name) {
  const label = root
    .findAll('label')
    .find((item) => item.text().trim() === name && item.attributes('for'))
  if (!label) throw new Error(`Missing field ${name}`)
  return root.get(`[id="${label.attributes('for')}"]`)
}
export async function choose(root, name, option) {
  await field(root, name).trigger('mousedown')
  await flushPromises()
  const item = [...document.querySelectorAll('[role="option"]')].find(
    (el) => el.textContent.trim() === option,
  )
  if (!item) throw new Error(`Missing option ${option}`)
  await new DOMWrapper(item).trigger('click')
  await flushPromises()
}
