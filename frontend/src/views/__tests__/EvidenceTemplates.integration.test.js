import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import CaseDashboard from '../CaseDashboard.vue'
import api from '../../services/api'
import { useAuthStore } from '../../stores/auth'
import { useActiveCaseStore } from '../../stores/activeCase'
import { mountWithVuetify } from '../../components/__tests__/helpers/vuetify'

const templatesUrl = '/api/admin/configuration/evidence-templates'
const templates = {
  Company: {
    name: 'Company investigation',
    description: 'Organized source material',
    folders: [
      {
        name: 'Records',
        description: 'Documents',
        subfolders: [{ name: 'Email', subfolders: [{ name: 'Archive' }] }, { name: 'Reports' }],
      },
      { name: 'Interviews' },
    ],
  },
  Empty: { name: 'Empty investigation', folders: [] },
}
const response = (config, data) => ({ config, data, status: 200, statusText: 'OK', headers: {} })
let originalAdapter
let adapter
let router
let pinia
let tree
let templateResponse
let applyResponse
let loadResponse
let requests

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  localStorage.clear()
  sessionStorage.clear()
  pinia = createPinia()
  setActivePinia(pinia)
  Object.assign(useAuthStore(), {
    isInitialized: true,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin' },
  })
  tree = []
  requests = []
  templateResponse = templates
  applyResponse = async () => ({ created: 5 })
  loadResponse = async () => ({ templates: templateResponse })
  originalAdapter = api.defaults.adapter
  adapter = vi.fn(async (config) => {
    requests.push(config)
    if (config.url === templatesUrl) return response(config, await loadResponse())
    if (config.url.endsWith('/apply-template')) return response(config, await applyResponse(config))
    if (config.url.endsWith('/folder-tree')) return response(config, structuredClone(tree))
    if (config.url === '/api/cases/') return response(config, [{ id: 42 }, { id: 77 }])
    if (/^\/api\/cases\/\d+$/.test(config.url))
      return response(config, {
        id: Number(config.url.split('/').at(-1)),
        case_number: 'TEMPLATE-CASE',
        title: 'Template case',
      })
    if (config.url.includes('/executions')) return response(config, [])
    throw new Error(`Unexpected request: ${config.url}`)
  })
  api.defaults.adapter = adapter
})

afterEach(() => {
  api.defaults.adapter = originalAdapter
  router?.options.history.destroy()
  pinia._s.forEach((store) => store.$dispose())
  localStorage.clear()
  sessionStorage.clear()
})

async function mountDashboard(caseId = 42, role = 'Admin') {
  useAuthStore().user.role = role
  await useActiveCaseStore().initialize(caseId)
  router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/case/:id', component: CaseDashboard }],
  })
  await router.push(`/case/${caseId}?tab=evidence`)
  const wrapper = mountWithVuetify(CaseDashboard, {
    attachTo: document.body,
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseDashboard: { template: '<main><slot /></main>' },
        CaseDetail: true,
        PluginExecutionHistory: true,
        EntityDataTable: true,
        CaseTasks: true,
        NoteEditor: true,
        EditCaseModal: true,
        ManageUsersModal: true,
        NewEntityModal: true,
        EntityDetailsModal: true,
        UploadEvidenceModal: true,
        MetadataModal: true,
        FileContentModal: true,
        FolderContextMenu: true,
        CreateFolderDialog: true,
        RenameDialog: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}
function namedButton(name, root = document.body) {
  const element = [...root.querySelectorAll('button')].find(
    (item) => item.textContent.trim() === name || item.getAttribute('aria-label') === name,
  )
  expect(element, `button named ${name}`).toBeDefined()
  return new DOMWrapper(element)
}
const dialog = () =>
  document.querySelector('[role="dialog"][aria-label="Select Evidence Folder Template"]')
async function openSelection() {
  await namedButton('Use Template').trigger('click')
  await flushPromises()
  expect(dialog()).not.toBeNull()
}
async function selectTemplate(name = 'Company investigation') {
  const input = new DOMWrapper(dialog().querySelector('[role="combobox"]'))
  await input.trigger('mousedown')
  await flushPromises()
  const option = [...document.querySelectorAll('[role="option"]')].find((item) =>
    item.textContent.includes(name),
  )
  expect(option, `template option ${name}`).toBeDefined()
  await new DOMWrapper(option).trigger('click')
  await flushPromises()
}
const applies = () => requests.filter((config) => config.url.endsWith('/apply-template'))
const refreshes = () => requests.filter((config) => config.url.endsWith('/folder-tree'))
function completeTree() {
  tree = [
    { id: 100, title: 'Records', is_folder: true, parent_folder_id: null },
    { id: 101, title: 'Email', is_folder: true, parent_folder_id: 100 },
    { id: 102, title: 'Interviews', is_folder: true, parent_folder_id: null },
  ]
}

describe('template selection through the real CaseDashboard Evidence refresh workflow', () => {
  it('shows loading and requires selection before an application; Cancel sends no write', async () => {
    await mountDashboard()
    let finish
    loadResponse = () =>
      new Promise((resolve) => {
        finish = () => resolve({ templates })
      })
    await openSelection()
    expect(dialog().textContent).toContain('Loading templates...')
    expect(namedButton('Apply Template').element.disabled).toBe(true)
    finish()
    await flushPromises()
    expect(dialog().textContent).not.toContain('Loading templates...')
    expect(namedButton('Apply Template').element.disabled).toBe(true)
    await namedButton('Cancel').trigger('click')
    await flushPromises()
    expect(document.querySelector('.v-dialog.v-overlay--active')).toBeNull()
    expect(applies()).toHaveLength(0)
  })

  it.each([
    [42, 'Admin'],
    [77, 'Investigator'],
  ])(
    'applies the selected hierarchy to Case %s for %s and renders the refreshed tree only after acknowledgement',
    async (caseId, role) => {
      const wrapper = await mountDashboard(caseId, role)
      await openSelection()
      await selectTemplate()
      for (const title of ['Records', 'Email', 'Archive', 'Reports', 'Interviews', 'Documents'])
        expect(dialog().textContent).toContain(title)
      let finish
      applyResponse = () =>
        new Promise((resolve) => {
          finish = () => {
            completeTree()
            resolve({ created: 3 })
          }
        })
      await namedButton('Apply Template').trigger('click')
      await flushPromises()
      expect(applies()).toHaveLength(1)
      expect(applies()[0]).toMatchObject({
        method: 'post',
        url: `/api/evidence/case/${caseId}/apply-template`,
        params: { template_name: 'Company' },
        data: 'null',
      })
      expect(refreshes()).toHaveLength(1)
      expect(wrapper.text()).toContain('No folders created yet')
      expect(namedButton('Apply Template').element.disabled).toBe(true)
      expect(namedButton('Cancel').element.disabled).toBe(true)
      namedButton('Apply Template').element.click()
      await flushPromises()
      expect(applies()).toHaveLength(1)
      finish()
      await flushPromises()
      expect(refreshes()).toHaveLength(2)
      expect(refreshes()[1].url).toBe(`/api/evidence/case/${caseId}/folder-tree`)
      expect(document.querySelector('.v-dialog.v-overlay--active')).toBeNull()
      expect(wrapper.get('[aria-label="Case evidence"]').text()).toContain('Records')
      expect(wrapper.get('[aria-label="Case evidence"]').text()).toContain('Interviews')
      await wrapper
        .findAll('.tree-item-title')
        .find((item) => item.text() === 'Records')
        .trigger('click')
      await flushPromises()
      expect(wrapper.get('[aria-label="Case evidence"]').text()).toContain('Email')
      expect(wrapper.text()).not.toContain('No folders created yet')
    },
  )

  it('recovers a failed template load and explains a selected empty hierarchy', async () => {
    await mountDashboard()
    loadResponse = vi
      .fn()
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockResolvedValue({ templates })
    await openSelection()
    expect(dialog().textContent).toContain('Failed to load templates')
    expect(dialog().textContent).not.toContain('Loading templates...')
    await namedButton('Retry').trigger('click')
    await flushPromises()
    await selectTemplate('Empty investigation')
    expect(dialog().textContent).toContain(
      'This template is empty. You can configure it in Admin settings.',
    )
    expect(applies()).toHaveLength(0)
  })

  it('keeps an empty template collection unselected and offers no application', async () => {
    templateResponse = {}
    await mountDashboard()
    await openSelection()
    await new DOMWrapper(dialog().querySelector('[role="combobox"]')).trigger('mousedown')
    await flushPromises()
    expect(document.body.textContent).toContain('No data available')
    expect(namedButton('Apply Template').element.disabled).toBe(true)
    expect(applies()).toHaveLength(0)
  })

  it('retains the target and selection after an application failure and refreshes only the successful retry', async () => {
    const wrapper = await mountDashboard()
    await openSelection()
    await selectTemplate()
    applyResponse = vi
      .fn()
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockImplementationOnce(async () => {
        completeTree()
        return { created: 3 }
      })
    await namedButton('Apply Template').trigger('click')
    await flushPromises()
    expect(dialog().textContent).toContain('Failed to apply template')
    expect(wrapper.text()).toContain('No folders created yet')
    expect(refreshes()).toHaveLength(1)
    await namedButton('Retry').trigger('click')
    await flushPromises()
    expect(dialog().textContent).toContain('Company investigation')
    expect(dialog().textContent).toContain('Template Preview')
    await namedButton('Apply Template').trigger('click')
    await flushPromises()
    expect(applies()).toHaveLength(2)
    expect(applies().map((config) => [config.url, config.params])).toEqual(
      Array(2).fill(['/api/evidence/case/42/apply-template', { template_name: 'Company' }]),
    )
    expect(refreshes()).toHaveLength(2)
    expect(wrapper.get('[aria-label="Case evidence"]').text()).toContain('Records')
    expect(document.querySelector('.v-dialog.v-overlay--active')).toBeNull()
  })

  it('closes template selection with Escape and restores keyboard focus to its named trigger', async () => {
    await mountDashboard()
    const trigger = namedButton('Use Template')
    trigger.element.focus()
    await openSelection()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(document.querySelector('.v-dialog.v-overlay--active')).toBeNull()
    expect(document.activeElement).toBe(trigger.element)
    expect(applies()).toHaveLength(0)
  })

  it('does not offer template application to an Analyst', async () => {
    const wrapper = await mountDashboard(42, 'Analyst')
    expect(wrapper.text()).toContain('No folders created yet')
    expect(wrapper.findAll('button').some((item) => item.text().trim() === 'Use Template')).toBe(
      false,
    )
    expect(applies()).toHaveLength(0)
    expect(requests.some((config) => config.url === templatesUrl)).toBe(false)
  })
})
