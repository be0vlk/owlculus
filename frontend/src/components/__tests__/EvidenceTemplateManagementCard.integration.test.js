import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import EvidenceTemplateManagementCard from '../EvidenceTemplateManagementCard.vue'
import api from '../../services/api'
import { mountWithVuetify } from './helpers/vuetify'

const url = '/api/admin/configuration/evidence-templates'
const folder = (name, subfolders = [], description = '') => ({ name, description, subfolders })
const fixture = () => ({
  Company: {
    name: 'Company investigation',
    folders: [
      folder('Records', [
        folder('Email', [folder('Archive')]),
        folder('Reports'),
        folder('Exports'),
      ]),
      folder('Sources'),
      folder('Untouched root'),
    ],
  },
  Person: { name: 'Person investigation', folders: [folder('Background')] },
})
const response = (config, data) => ({ config, data, status: 200, statusText: 'OK', headers: {} })
const failure = () =>
  Promise.reject({ response: { status: 500, data: { detail: 'Temporarily unavailable' } } })
let adapter
let originalAdapter
let saved
let templates

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  vi.spyOn(console, 'error').mockImplementation(() => {})
  templates = fixture()
  saved = []
  originalAdapter = api.defaults.adapter
  adapter = vi.fn(async (config) => {
    if (config.url !== url) throw new Error(`Unexpected request: ${config.url}`)
    if (config.method === 'put') saved.push(JSON.parse(config.data))
    return response(config, { templates: structuredClone(templates) })
  })
  api.defaults.adapter = adapter
})

afterEach(() => {
  api.defaults.adapter = originalAdapter
  vi.clearAllTimers()
  vi.useRealTimers()
  localStorage.clear()
  sessionStorage.clear()
})

const button = (wrapper, name) =>
  wrapper.findAll('button').find((item) => item.text().trim() === name)
async function mountEditor() {
  const wrapper = mountWithVuetify(EvidenceTemplateManagementCard, { attachTo: document.body })
  await wrapper.get('.v-expansion-panel-title').trigger('click')
  await flushPromises()
  return wrapper
}
function row(wrapper, name) {
  return wrapper
    .findAll('.folder-row')
    .find((item) => item.get('input[placeholder="Folder name"]').element.value === name)
}
async function edit(wrapper, name, value, description = false) {
  const input = row(wrapper, name).get(
    description
      ? 'input[placeholder="Description (optional)"]'
      : 'input[placeholder="Folder name"]',
  )
  await input.setValue(value)
  await input.trigger('blur')
}
async function iconAction(wrapper, name, icon) {
  // Existing folder icon actions have no accessible names: separate failing reproduction below.
  await row(wrapper, name)
    .findAll('button')
    .find((item) => item.find(`.${icon}`).exists())
    .trigger('click')
}

describe('Evidence folder template management over HTTP', () => {
  it('shows loading until the template response arrives', async () => {
    let finish
    adapter.mockImplementationOnce(
      (config) =>
        new Promise((resolve) => {
          finish = () => resolve(response(config, { templates }))
        }),
    )
    const wrapper = await mountEditor()
    expect(wrapper.find('.v-skeleton-loader').exists()).toBe(true)
    expect(wrapper.find('input').exists()).toBe(false)
    finish()
    await flushPromises()
    expect(wrapper.find('.v-skeleton-loader').exists()).toBe(false)
    expect(row(wrapper, 'Records')).toBeDefined()
    expect(adapter).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ method: 'get', url }))
  })

  it('loads again after failure and distinguishes a template with no folders', async () => {
    templates.Company.folders = []
    adapter.mockImplementationOnce(failure)
    const wrapper = await mountEditor()
    expect(wrapper.text()).toContain('Failed to load templates')
    expect(wrapper.find('.v-skeleton-loader').exists()).toBe(false)
    await button(wrapper, 'Retry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('No Folder Structure')
    expect(wrapper.text()).not.toContain('Failed to load templates')
    await button(wrapper, 'Add Folder').trigger('click')
    expect(row(wrapper, 'New Folder')).toBeDefined()
  })

  it('edits roots and nested descendants, adds subfolders, and preserves siblings and other templates in the saved hierarchy', async () => {
    const wrapper = await mountEditor()
    await edit(wrapper, 'Records', 'Collected records')
    await edit(wrapper, 'Collected records', 'Primary source material', true)
    await edit(wrapper, 'Archive', 'Historical mail')
    await iconAction(wrapper, 'Email', 'mdi-folder-plus')
    await edit(wrapper, 'New Subfolder', 'Recent mail')
    await iconAction(wrapper, 'Reports', 'mdi-delete')
    await iconAction(wrapper, 'Sources', 'mdi-delete')
    await button(wrapper, 'Add Folder').trigger('click')
    await edit(wrapper, 'New Folder', 'Interviews')
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()

    expect(saved).toEqual([
      {
        templates: {
          Company: {
            name: 'Company investigation',
            folders: [
              folder(
                'Collected records',
                [
                  folder('Email', [folder('Historical mail'), folder('Recent mail')]),
                  folder('Exports'),
                ],
                'Primary source material',
              ),
              folder('Untouched root'),
              folder('Interviews'),
            ],
          },
          Person: fixture().Person,
        },
      },
    ])
    expect(wrapper.text()).toContain('Templates saved successfully!')
  })

  it('disables repeated saves and waits for acknowledgement before success', async () => {
    const wrapper = await mountEditor()
    let finish
    adapter.mockImplementationOnce(
      (config) =>
        new Promise((resolve) => {
          finish = () => resolve(response(config, {}))
        }),
    )
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()
    const save = button(wrapper, 'Save Changes')
    expect(save.element.disabled).toBe(true)
    save.element.click()
    await flushPromises()
    expect(adapter.mock.calls.filter(([config]) => config.method === 'put')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('Templates saved successfully!')
    finish()
    await flushPromises()
    expect(button(wrapper, 'Save Changes').element.disabled).toBe(false)
    expect(wrapper.text()).toContain('Templates saved successfully!')
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.text()).not.toContain('Templates saved successfully!')
  })

  it('exposes a failed save without success and allows resubmitting the retained draft', async () => {
    const wrapper = await mountEditor()
    await edit(wrapper, 'Records', 'Retained draft')
    adapter.mockImplementationOnce(failure)
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to save templates')
    expect(wrapper.text()).not.toContain('Templates saved successfully!')
    expect(button(wrapper, 'Save Changes').element.disabled).toBe(false)
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()
    expect(saved[0].templates.Company.folders[0].name).toBe('Retained draft')
    expect(row(wrapper, 'Retained draft')).toBeDefined()
    expect(wrapper.text()).toContain('Templates saved successfully!')
  })

  // Defect: .scratch/frontend-test-coverage-defects/issues/04-templates-save-retry-discards-draft.md
  it.fails('retains the edited draft when the failed-save Retry control is used', async () => {
    const wrapper = await mountEditor()
    await edit(wrapper, 'Records', 'Retained draft')
    adapter.mockImplementationOnce(failure)
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to save templates')
    await button(wrapper, 'Retry').trigger('click')
    await flushPromises()
    await button(wrapper, 'Save Changes').trigger('click')
    await flushPromises()
    expect(saved[0].templates.Company.folders[0].name).toBe('Retained draft')
  })

  // Defect: .scratch/frontend-test-coverage-defects/issues/04-templates-missing-empty-state.md
  it.fails('provides a clear empty state when the server returns no templates', async () => {
    templates = {}
    const wrapper = await mountEditor()
    expect(wrapper.text()).toMatch(/no (?:folder )?templates|no folder structure/i)
  })

  // Defect: .scratch/frontend-test-coverage-defects/issues/04-templates-unnamed-folder-actions.md
  it.fails(
    'names the recursive folder editor actions for keyboard and assistive technology users',
    async () => {
      const wrapper = await mountEditor()
      const actions = row(wrapper, 'Records').findAll('button')
      expect(actions).toHaveLength(3)
      for (const action of actions) {
        expect(
          action.attributes('aria-label') ||
            action.attributes('aria-labelledby') ||
            action.text().trim(),
        ).toBeTruthy()
      }
    },
  )
})
