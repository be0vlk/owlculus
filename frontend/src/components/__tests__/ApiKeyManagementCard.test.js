import { expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import ApiKeyManagementCard from '../ApiKeyManagementCard.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

it('does not report success for an invalid API-key keyboard submission', async () => {
  api.get.mockResolvedValue({ data: {} })
  const wrapper = mountWithVuetify(ApiKeyManagementCard, { attachTo: document.body })
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Add API Key')
    .trigger('click')
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"][aria-label="Add API Key"]'))
  const submit = dialog.findAll('button').find((button) => button.text() === 'Add API Key')
  expect(submit.element.form).toBe(dialog.get('form').element)
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(api.put).not.toHaveBeenCalled()
  expect(wrapper.emitted('notification')).toBeUndefined()
  expect(dialog.text()).toContain('Provider is required')
  expect(dialog.text()).toContain('API key is required')
})
