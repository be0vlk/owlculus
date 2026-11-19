import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import ApiKeyManagementCard from '../ApiKeyManagementCard.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

let wrapper
beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: { shodan: { name: 'Shodan API' } } })
})
afterEach(() => wrapper?.unmount())

async function mountCard() {
  wrapper = mountWithVuetify(ApiKeyManagementCard, { attachTo: document.body })
  await flushPromises()
  return wrapper
}
const dialog = () => new DOMWrapper(document.querySelector('[role="dialog"]'))
const button = (root, text) => root.findAll('button').find((item) => item.text() === text)

const actions = {
  async add() {
    await button(wrapper, 'Add API Key').trigger('click')
    await flushPromises()
    wrapper.findComponent({ name: 'VSelect' }).vm.$emit('update:modelValue', 'virustotal')
    await flushPromises()
    await dialog().get('input[type="password"]').setValue('long-enough-key')
    await dialog().get('form').trigger('submit')
  },
  async update() {
    await wrapper.get('[aria-label="Edit Shodan API Key"]').trigger('click')
    await flushPromises()
    await dialog().get('form').trigger('submit')
  },
  async delete() {
    await wrapper.get('[aria-label="Delete Shodan API Key"]').trigger('click')
    await wrapper.emitted('confirmDelete')[0][0].onConfirm()
  },
}

it('does not report success for an invalid API-key keyboard submission', async () => {
  api.get.mockResolvedValue({ data: {} })
  await mountCard()
  await button(wrapper, 'Add API Key').trigger('click')
  await flushPromises()
  const form = new DOMWrapper(
    document.querySelector('[role="dialog"][aria-label="Add API Key"]'),
  ).get('form')
  const submit = dialog()
    .findAll('button')
    .find((item) => item.text() === 'Add API Key')
  expect(submit.element.form).toBe(form.element)
  await form.trigger('submit')
  await flushPromises()
  expect(api.put).not.toHaveBeenCalled()
  expect(wrapper.emitted('notification')).toBeUndefined()
  expect(dialog().text()).toContain('Provider is required')
  expect(dialog().text()).toContain('API key is required')
})

it('adds and edits through the same PUT, keeping the stored key when none is entered', async () => {
  await mountCard()
  api.put.mockResolvedValue({})
  await actions.add()
  await flushPromises()
  await actions.update()
  await flushPromises()
  expect(api.put.mock.calls).toEqual([
    [
      '/api/admin/configuration/api-keys/virustotal',
      { name: 'VirusTotal API', api_key: 'long-enough-key' },
    ],
    ['/api/admin/configuration/api-keys/shodan', { name: 'Shodan API' }],
  ])
  expect(wrapper.emitted('notification')).toEqual([
    [{ text: 'API key added successfully!', color: 'success' }],
    [{ text: 'API key updated successfully!', color: 'success' }],
  ])
})

it.each(['add', 'update', 'delete'])(
  'reports %s failures with the server detail or a fallback and re-enables the actions',
  async (verb) => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const method = verb === 'delete' ? 'delete' : 'put'
    for (const [failure, message] of [
      [{ response: { data: { detail: 'Provider is unavailable' } } }, 'Provider is unavailable'],
      [new Error('Network unavailable'), `Failed to ${verb} API key`],
    ]) {
      await mountCard()
      api[method].mockRejectedValueOnce(failure)
      await actions[verb]()
      await flushPromises()
      expect(wrapper.emitted('notification')).toEqual([[{ text: message, color: 'error' }]])
      expect(wrapper.get('[aria-label="Edit Shodan API Key"]').element.disabled).toBe(false)
      wrapper.unmount()
      wrapper = null
    }
  },
)
