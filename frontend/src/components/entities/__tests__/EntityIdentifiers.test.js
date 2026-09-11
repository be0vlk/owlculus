import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NewEntityModal from '../../NewEntityModal.vue'
import EntityDetailsModal from '../EntityDetailsModal.vue'
import { entityService } from '@/services/entity'

vi.mock('@/services/entity', () => ({
  entityService: {
    getDuplicateAdvisories: vi.fn().mockResolvedValue([]),
    updateEntity: vi.fn(),
    createEntity: vi.fn(),
  },
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

it.each([
  ['Person', 'Email', 'lead@example.com'],
  ['Person', 'Phone', '+1 (555) 123-4567'],
  ['Person', 'Employer', 'Acme'],
  ['Person', 'Profile URL', 'https://example.com/profile'],
  ['Vehicle', 'VIN', 'known-vin'],
  ['Vehicle', 'License Plate', 'ABC'],
])('creates an unnamed %s using %s', async (kind, label, value) => {
  wrapper = mount(NewEntityModal, {
    props: { show: true, caseId: '7' },
    attachTo: document.body,
    global: {
      plugins: [createVuetify({ components, directives, theme: false })],
      stubs: { VDialog: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  await tab(kind)
  await input(label).setValue(value)
  entityService.createEntity.mockImplementation(async (_case, payload) => ({ id: 9, ...payload }))
  await button('Add Entity').trigger('click')
  await flushPromises()
  expect(entityService.createEntity).toHaveBeenCalled()
  expect(wrapper.emitted('created')[0][0].id).toBe(9)
})

it.each(['create', 'edit'])(
  'shows candidates and permits intentional separation on %s',
  async (mode) => {
    const candidate = {
      id: 12,
      label: 'Ada',
      identifiers: { email: 'existing@example.com' },
      reason: 'Same name; this may be a different Person.',
      blocking: false,
    }
    entityService.getDuplicateAdvisories.mockResolvedValueOnce([candidate])
    if (mode === 'create') {
      wrapper = mount(NewEntityModal, {
        props: { show: true, caseId: '7' },
        attachTo: document.body,
        global: {
          plugins: [createVuetify({ components, directives, theme: false })],
          stubs: { VDialog: { template: '<div><slot /></div>' } },
        },
      })
      await flushPromises()
      await input('First Name').setValue('Ada')
    } else {
      await openEntity({ id: 9, entity_type: 'person', data: { first_name: 'Ada' } })
      await button('Edit Entity').trigger('click')
    }
    const write = mode === 'create' ? entityService.createEntity : entityService.updateEntity
    write.mockImplementation(async (...args) => ({ id: 9, ...args.at(-1) }))
    await button(mode === 'create' ? 'Add Entity' : 'Save Changes').trigger('click')
    await flushPromises()
    expect(write).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('existing@example.com')
    expect(wrapper.get('a').attributes('href')).toBe('/case/7?entity=12')
    await button('Keep separate Person').trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledTimes(1)
    if (mode === 'edit')
      expect(entityService.getDuplicateAdvisories).toHaveBeenCalledWith(7, expect.any(Object), 9)
  },
)

it.each([
  ['person', { email: 'lead@example.com' }, 'lead@example.com'],
  ['person', { phone: '+15551234567' }, '+15551234567'],
  ['person', { employer: 'Acme' }, 'Acme'],
  [
    'person',
    { social_media: { other: 'https://example.com/profile' } },
    'https://example.com/profile',
  ],
  ['vehicle', { vin: 'known-vin' }, 'known-vin'],
  ['vehicle', { license_plate: 'ABC' }, 'ABC'],
])('labels and edits incomplete %s', async (entity_type, data, label) => {
  await openEntity({ id: 9, entity_type, data })
  expect(wrapper.get('#entity-details-dialog-title').text()).toBe(label)
  await button('Edit Entity').trigger('click')
  entityService.updateEntity.mockImplementation(async (_case, id, payload) => ({ id, ...payload }))
  await button('Save Changes').trigger('click')
  await flushPromises()
  expect(entityService.updateEntity).toHaveBeenCalledWith(
    7,
    9,
    expect.objectContaining({ data: expect.objectContaining(data) }),
  )
})

it.each(['Person', 'Vehicle'])('rejects blank %s creation', async (kind) => {
  wrapper = mount(NewEntityModal, {
    props: { show: true, caseId: '7' },
    attachTo: document.body,
    global: {
      plugins: [createVuetify({ components, directives, theme: false })],
      stubs: { VDialog: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  await tab(kind)
  await input(kind === 'Person' ? 'First Name' : 'VIN').setValue('  ')
  expect(button('Add Entity').attributes('disabled')).toBeDefined()
  expect(wrapper.text()).toContain('Provide a')
})

it.each([
  ['person', 'Basic Information', 'First Name', { first_name: 'Ada' }],
  ['vehicle', 'Vehicle Information', 'VIN', { vin: 'known-vin' }],
])('rejects clearing the last useful %s field on edit', async (entity_type, title, label, data) => {
  await openEntity({ id: 9, entity_type, data })
  await button('Edit Entity').trigger('click')
  await tab(title)
  await input(label).setValue('   ')
  await button('Save Changes').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Provide a')
  expect(entityService.updateEntity).not.toHaveBeenCalled()
})

it('clears candidate summaries when a later advisory request is denied', async () => {
  await openEntity({ id: 9, entity_type: 'person', data: { first_name: 'Ada' } })
  await button('Edit Entity').trigger('click')
  entityService.getDuplicateAdvisories.mockResolvedValueOnce([
    { id: 12, label: 'Formerly visible', identifiers: {}, reason: 'Same name', blocking: false },
  ])
  await button('Save Changes').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Formerly visible')
  entityService.getDuplicateAdvisories.mockRejectedValueOnce(new Error('Access denied'))
  await button('Save Changes').trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('Formerly visible')
  expect(wrapper.text()).toContain('Access denied')
  expect(entityService.updateEntity).not.toHaveBeenCalled()
})

it.each(['192.0.2.1', '2001:db8::1', '2001:0DB8:0000:0000:0000:0000:0000:0001'])(
  'submits %s through the create and edit IP forms',
  async (ip_address) => {
    wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '7' },
      attachTo: document.body,
      global: {
        plugins: [createVuetify({ components, directives, theme: false })],
        stubs: { VDialog: { template: '<div><slot /></div>' } },
      },
    })
    await flushPromises()
    await tab('IP Address')
    await input('IP Address').setValue(ip_address)
    entityService.createEntity.mockResolvedValue({
      id: 9,
      entity_type: 'ip_address',
      data: { ip_address },
    })
    await button('Add Entity').trigger('click')
    await flushPromises()
    expect(entityService.createEntity).toHaveBeenCalledWith(
      '7',
      expect.objectContaining({ data: expect.objectContaining({ ip_address }) }),
    )
    wrapper.unmount()
    await openEntity({ id: 9, entity_type: 'ip_address', data: { ip_address: '192.0.2.2' } })
    await button('Edit Entity').trigger('click')
    await tab('IP Address Information')
    await input('IP Address').setValue(ip_address)
    entityService.updateEntity.mockResolvedValue({
      id: 9,
      entity_type: 'ip_address',
      data: { ip_address },
    })
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenCalledWith(
      7,
      9,
      expect.objectContaining({ data: expect.objectContaining({ ip_address }) }),
    )
  },
)

it.each(['fe80::1%eth0', '2001:db8::/64', 'IP: 2001:db8::1', '192.168.001.1', '[::1]'])(
  'rejects unsupported IP input %s in the edit form',
  async (ip_address) => {
    await openEntity({ id: 9, entity_type: 'ip_address', data: { ip_address: '192.0.2.1' } })
    await button('Edit Entity').trigger('click')
    await tab('IP Address Information')
    await input('IP Address').setValue(ip_address)
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Please enter a valid IPv4 or IPv6 address')
    expect(entityService.updateEntity).not.toHaveBeenCalled()
  },
)
