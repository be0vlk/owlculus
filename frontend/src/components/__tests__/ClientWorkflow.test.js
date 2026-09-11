import { expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import NewClientModal from '../NewClientModal.vue'
import EditClientModal from '../EditClientModal.vue'
import { clientService } from '@/services/client'

vi.mock('@/services/client', () => ({
  clientService: { createClient: vi.fn(), updateClient: vi.fn() },
}))
let wrapper
it('validates client submissions and preserves entered values after failure', async () => {
  wrapper = mountWithVuetify(NewClientModal, {
    props: { isOpen: false },
    attachTo: document.body,
  })
  await wrapper.setProps({ isOpen: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.attributes('aria-label')).toBe('New Client')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(clientService.createClient).not.toHaveBeenCalled()
  expect(dialog.text()).toContain('Name is required')
  const fields = dialog.findAll('input, textarea')
  for (const [index, value] of ['Acme', 'contact@example.org', '555-0100', '1 Main St'].entries()) {
    await fields[index].setValue(value)
  }
  vi.spyOn(console, 'error').mockImplementation(() => {})
  clientService.createClient.mockRejectedValueOnce(new Error('Unavailable'))
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(dialog.get('[role="alert"]').text()).toContain('Failed to create client')
  expect(fields[0].element.value).toBe('Acme')
  clientService.createClient.mockResolvedValueOnce({ id: 7, name: 'Acme' })
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('created')).toEqual([[{ id: 7, name: 'Acme' }]])
})

it('allows clients with no optional contact details', async () => {
  wrapper = mountWithVuetify(NewClientModal, { props: { isOpen: false }, attachTo: document.body })
  await wrapper.setProps({ isOpen: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  await dialog.get('input').setValue('Name Only')
  clientService.createClient.mockResolvedValue({ id: 8, name: 'Name Only' })
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(clientService.createClient).toHaveBeenLastCalledWith({
    name: 'Name Only',
    email: null,
    phone: '',
    address: '',
  })
  expect(wrapper.emitted('created')).toEqual([[{ id: 8, name: 'Name Only' }]])
})

it('edits existing clients without requiring optional contacts', async () => {
  wrapper = mountWithVuetify(EditClientModal, {
    props: { isOpen: false, client: { id: 4, name: 'Existing Client' } },
    attachTo: document.body,
  })
  await wrapper.setProps({ isOpen: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  await dialog.get('input').setValue('Updated Client')
  clientService.updateClient.mockResolvedValue({ id: 4, name: 'Updated Client' })
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(clientService.updateClient).toHaveBeenCalledWith(4, {
    name: 'Updated Client',
    email: null,
    phone: '',
    address: '',
  })
  expect(wrapper.emitted('updated')).toEqual([[{ id: 4, name: 'Updated Client' }]])
})
