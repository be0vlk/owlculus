import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NewEntityModal from '../../NewEntityModal.vue'
import EntityDetailsModal from '../EntityDetailsModal.vue'
import { entityService } from '@/services/entity'

vi.mock('@/services/entity', () => ({
  entityService: { updateEntity: vi.fn(), createEntity: vi.fn() },
}))
let wrapper
let warningSpy

beforeEach(() => {
  vi.clearAllMocks()
  warningSpy = vi.spyOn(console, 'warn')
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  vi.stubGlobal('visualViewport', new EventTarget())
})

afterEach(() => {
  wrapper?.unmount()
  expect(warningSpy.mock.calls.flat().join(' ')).not.toContain('Duplicate extension names')
  warningSpy.mockRestore()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

async function openEntity(entity) {
  wrapper = mount(EntityDetailsModal, {
    props: { show: true, entity, caseId: 7, existingEntities: [] },
    attachTo: document.body,
    global: {
      plugins: [createVuetify({ components, directives, theme: false })],
      stubs: { VDialog: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  await wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text() === 'Notes')
    .trigger('click')
  await flushPromises()
}

const textbox = () => wrapper.get('[role="textbox"][aria-label="Entity notes"]')
const button = (text) => wrapper.findAll('button').find((item) => item.text() === text)

async function tab(title) {
  await wrapper
    .findAll('[role="tab"]')
    .find((item) => item.text() === title)
    .trigger('click')
  await flushPromises()
}

function input(label) {
  const field = wrapper
    .findAll('.v-input')
    .find((item) => item.findAll('label').some((item) => item.text() === label))
  return field.get('input, textarea')
}

async function typeNotes(html) {
  textbox().element.innerHTML = html
  await textbox().trigger('input')
}

describe('Domain input and website edits', () => {
  it.each([
    'l·l.cat',
    'xn--ll-0ea.cat',
    'service.123',
    'example.co.uk',
    'login.example.com',
    'bücher.example',
    'XN--BCHER-KVA.example.',
  ])('accepts %s in the actual create form', async (domain) => {
    wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '7' },
      attachTo: document.body,
      global: {
        plugins: [createVuetify({ components, directives, theme: false })],
        stubs: { VDialog: { template: '<div><slot /></div>' } },
      },
    })
    await flushPromises()
    await tab('Domain')
    await input('Domain Name').setValue(domain)
    await input('Domain Name').trigger('blur')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Please enter a valid domain name')
    entityService.createEntity.mockResolvedValue({
      id: 9,
      entity_type: 'domain',
      data: { domain },
    })
    await button('Add Entity').trigger('click')
    await flushPromises()
    expect(entityService.createEntity).toHaveBeenCalledWith(
      '7',
      expect.objectContaining({ data: expect.objectContaining({ domain }) }),
    )
  })

  it.each([
    'bad_label.example',
    '-bad.example',
    'bad-.example',
    'bad..example',
    'example.com/path',
  ])('shows a clear error and prevents saving %s in the edit form', async (domain) => {
    await openEntity({ id: 9, entity_type: 'domain', data: { domain: 'example.com' } })
    await button('Edit Entity').trigger('click')
    await tab('Domain Information')
    await input('Domain Name').setValue(domain)
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Please enter a valid domain name')
    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it.each([
    'l·l.cat',
    'xn--ll-0ea.cat',
    'service.123',
    'example.co.uk',
    'login.example.com',
    'bücher.example',
    'example.com.',
  ])('accepts %s in the edit form', async (domain) => {
    await openEntity({ id: 9, entity_type: 'domain', data: { domain: 'example.com' } })
    await button('Edit Entity').trigger('click')
    await tab('Domain Information')
    await input('Domain Name').setValue(domain)
    entityService.updateEntity.mockImplementation(async (_case, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('edit').at(-1)[0].data.domain).toBe(domain)
  })

  it.each([
    'bad_label.example',
    '-bad.example',
    'bad-.example',
    'bad..example',
    'example.com/path',
  ])('rejects %s in the create form', async (domain) => {
    wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '7' },
      attachTo: document.body,
      global: {
        plugins: [createVuetify({ components, directives, theme: false })],
        stubs: { VDialog: { template: '<div><slot /></div>' } },
      },
    })
    await flushPromises()
    await tab('Domain')
    await input('Domain Name').setValue(domain)
    await input('Domain Name').trigger('blur')
    await flushPromises()
    expect(wrapper.text()).toContain('Please enter a valid domain name')
    expect(button('Add Entity').attributes('disabled')).toBeDefined()
    expect(entityService.createEntity).not.toHaveBeenCalled()
  })

  it('preserves an HTTP website during ordinary notes and form saves', async () => {
    const website = 'http://example.com:8080/path?q=1#f'
    await openEntity({
      id: 9,
      entity_type: 'company',
      data: { name: 'Company', website, notes: '' },
    })
    entityService.updateEntity.mockImplementation(async (_case, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Edit Entity').trigger('click')
    await typeNotes('<p>Investigation notes</p>')
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('edit').at(-1)[0].data.website).toBe(website)
    await button('Edit Entity').trigger('click')
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('edit').at(-1)[0].data.website).toBe(website)
  })
})
