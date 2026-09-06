import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import EntityDetailsModal from '../EntityDetailsModal.vue'
import { entityService } from '@/services/entity'

vi.mock('@/services/entity', () => ({ entityService: { updateEntity: vi.fn() } }))
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

async function openNotes(entity) {
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

function deferSaves() {
  const writes = []
  entityService.updateEntity.mockImplementation(
    (_caseId, id, payload) =>
      new Promise((resolve, reject) => {
        writes.push({
          succeed: () => resolve({ id, ...payload }),
          fail: () => reject(new Error('Unavailable')),
        })
      }),
  )
  return writes
}

describe('Entity notes with the real editor', () => {
  it('retains a failed form draft while later queued notes save only acknowledged fields', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: {
        address: { city: 'Old', country: 'UK' },
        sources: { 'address.city': 'Old source' },
        notes: '<p>Initial</p>',
      },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('Draft city')
    await input('Source for City').setValue('Draft source')
    await tab('Notes')
    vi.useFakeTimers()
    const writes = deferSaves()
    await typeNotes('<p>Form <em>notes</em></p>')
    await button('Save Changes').trigger('click')
    await typeNotes('<p>Later <strong>notes</strong></p>')
    await vi.advanceTimersByTimeAsync(5000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    writes[0].fail()
    await flushPromises()
    expect(wrapper.text()).toContain('Unavailable')
    expect(textbox().attributes('contenteditable')).toBe('true')
    expect(textbox().get('strong').text()).toBe('notes')
    expect(wrapper.emitted('edit')).toBeUndefined()
    expect(entityService.updateEntity.mock.calls[1]).toEqual([
      7,
      9,
      {
        entity_type: 'person',
        data: { ...entity.data, notes: '<p>Later <strong>notes</strong></p>' },
      },
    ])
    writes[1].succeed()
    await flushPromises()
    await tab('Address')
    expect(input('City').element.value).toBe('Draft city')
    expect(input('Source for City').element.value).toBe('Draft source')
    await button('Save Changes').trigger('click')
    writes[2].succeed()
    await flushPromises()
    expect(wrapper.text()).toContain('View Mode')
    expect(wrapper.text()).not.toContain('Unavailable')
    expect(wrapper.emitted('edit').at(-1)[0].data).toMatchObject({
      address: { city: 'Draft city', country: 'UK' },
      sources: { 'address.city': 'Draft source' },
      notes: '<p>Later <strong>notes</strong></p>',
    })
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(3)
  })

  it('runs a queued form save after autosave fails and retains its current notes', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { address: { city: 'Old' }, notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    vi.useFakeTimers()
    const writes = deferSaves()
    await typeNotes('<p>Autosave notes</p>')
    await vi.advanceTimersByTimeAsync(5000)
    await tab('Address')
    await input('City').setValue('New')
    await input('Source for City').setValue('New source')
    await tab('Notes')
    await typeNotes('<p>Submitted notes</p>')
    await button('Save Changes').trigger('click')
    writes[0].fail()
    await flushPromises()
    expect(textbox().text()).toBe('Submitted notes')
    expect(wrapper.emitted('edit')).toBeUndefined()
    expect(entityService.updateEntity.mock.calls[1][2].data).toMatchObject({
      address: { city: 'New' },
      sources: { 'address.city': 'New source' },
      notes: '<p>Submitted notes</p>',
    })
    writes[1].succeed()
    await flushPromises()
    expect(wrapper.text()).toContain('View Mode')
    expect(wrapper.text()).not.toContain('Failed to save')
    expect(wrapper.emitted('edit')).toHaveLength(1)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
  })

  it('saves a populated nested city and reopens the acknowledged value without a parent refresh', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', address: { city: 'Old', country: 'UK' }, notes: '' },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    await tab('Address')
    expect(input('City').element.value).toBe('Old')
    await input('City').setValue('New')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    const saved = wrapper.emitted('edit').at(-1)[0]
    expect(saved.data.address).toEqual({ city: 'New', country: 'UK' })
    expect(entity.data.address).toEqual({ city: 'Old', country: 'UK' })
    await button('Edit Entity').trigger('click')
    expect(input('City').element.value).toBe('New')
    wrapper.unmount()
    await openNotes(saved)
    await button('Edit Entity').trigger('click')
    await tab('Address')
    expect(input('City').element.value).toBe('New')
  })

  it.each(['person', 'company'])(
    'saves %s fields and provenance across tabs without losing stored collections',
    async (entity_type) => {
      const entity = {
        id: 9,
        entity_type,
        data: {
          first_name: 'Ada',
          name: 'Acme',
          notes: '',
          aliases: ['Original alias'],
          address: { city: 'Old', country: 'UK', street: 'Remove me' },
          social_media: { bluesky: 'old.example', discord: 'Keep me' },
          sources: {
            'address.city': 'Old source',
            'address.street': 'Remove source',
            name: 'Registry',
          },
          associates: { friends: 'Sam' },
          executives: { ceo: 'Old CEO', cfo: 'Keep CFO' },
          affiliates: { subsidiaries: 'Keep subsidiary' },
          imported: { records: [{ value: 'Keep imported data' }] },
        },
      }
      const original = JSON.parse(JSON.stringify(entity))
      await openNotes(entity)
      await button('Edit Entity').trigger('click')
      await tab('Address')
      expect(input('Source for City').element.value).toBe('Old source')
      expect(entityService.updateEntity).not.toHaveBeenCalled()
      await input('City').setValue('New')
      await input('State').setValue('New state')
      await input('Street').setValue('')
      await input('Source for City').setValue('New source')
      await input('Source for State').setValue('New state source')
      await input('Source for Street').setValue('')
      await tab('Social Media')
      await input('Bluesky').setValue('')
      await input('LinkedIn').setValue('https://example.com/profile')
      if (entity_type === 'company') {
        await tab('Executives')
        await input('CEO').setValue('New CEO')
        await tab('Affiliates')
        await input('Parent Company').setValue('New parent')
      }
      await tab('Address')
      expect(input('City').element.value).toBe('New')
      expect(entity).toEqual(original)
      entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
        id,
        ...payload,
      }))
      await button('Save Changes').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('View Mode')
      const saved = wrapper.emitted('edit').at(-1)[0]
      expect(saved.data).toMatchObject({
        address: { city: 'New', country: 'UK', state: 'New state' },
        social_media: { discord: 'Keep me', linkedin: 'https://example.com/profile' },
        sources: {
          'address.city': 'New source',
          'address.state': 'New state source',
          name: 'Registry',
        },
        aliases: ['Original alias'],
        associates: { friends: 'Sam' },
        imported: { records: [{ value: 'Keep imported data' }] },
      })
      expect(saved.data.address).not.toHaveProperty('street')
      expect(saved.data.social_media).not.toHaveProperty('bluesky')
      expect(Object.keys(saved.data.sources)).not.toContain('address.street')
      expect(Object.keys(saved.data)).not.toContain('address.city')
      if (entity_type === 'company') {
        expect(saved.data.executives).toEqual({ ceo: 'New CEO', cfo: 'Keep CFO' })
        expect(saved.data.affiliates).toEqual({
          subsidiaries: 'Keep subsidiary',
          parent_company: 'New parent',
        })
      }
      expect(entity).toEqual(original)
      wrapper.unmount()
      await openNotes(saved)
      await button('Edit Entity').trigger('click')
      await tab('Address')
      expect(input('City').element.value).toBe('New')
      expect(input('Street').element.value).toBe('')
      expect(input('Source for City').element.value).toBe('New source')
      await tab('Social Media')
      expect(input('Bluesky').element.value).toBe('')
      expect(input('LinkedIn').element.value).toBe('https://example.com/profile')
    },
  )

  it.each([false, true])(
    'isolates Cancelled fields and sources with note autosave=%s',
    async (autosave) => {
      const entity = {
        id: 9,
        entity_type: 'person',
        data: {
          first_name: 'Ada',
          notes: '<p>Initial</p>',
          address: { city: 'Old' },
          sources: { 'address.city': 'Saved source', 'address.country': 'Country source' },
        },
      }
      const original = JSON.parse(JSON.stringify(entity))
      await openNotes(entity)
      await button('Edit Entity').trigger('click')
      await tab('Address')
      await input('City').setValue('Unsaved')
      await input('Source for City').setValue('Unsaved source')
      await input('Source for State').setValue('Unsaved new source')
      await input('Source for Country').setValue('')
      expect(entity).toEqual(original)
      await tab('Notes')
      vi.useFakeTimers()
      entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
        id,
        ...payload,
      }))
      if (autosave) {
        textbox().element.innerHTML = '<p>Saved notes</p>'
        await textbox().trigger('input')
        await vi.advanceTimersByTimeAsync(4999)
        expect(entityService.updateEntity).not.toHaveBeenCalled()
        await vi.advanceTimersByTimeAsync(1)
        expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
          entity_type: 'person',
          data: { ...original.data, notes: '<p>Saved notes</p>' },
        })
      }
      await button('Cancel').trigger('click')
      await flushPromises()
      expect(entity).toEqual(original)
      expect(textbox().text()).toBe(autosave ? 'Saved notes' : 'Initial')
      await button('Edit Entity').trigger('click')
      await tab('Address')
      expect(input('City').element.value).toBe('Old')
      expect(input('Source for City').element.value).toBe('Saved source')
      expect(input('Source for Country').element.value).toBe('Country source')
      expect(input('Source for State').element.value).toBe('')
      expect(entityService.updateEntity).toHaveBeenCalledTimes(autosave ? 1 : 0)
    },
  )

  it.each([
    ['domain', 'Domain Information', 'Domain Name', 'domain', 'old.example', 'new.example'],
    ['ip_address', 'IP Address Information', 'IP Address', 'ip_address', '192.0.2.1', '192.0.2.2'],
    ['network_assets', 'Network Assets', 'Subdomains', 'subdomains', 'old.example', 'new.example'],
    ['vehicle', 'Vehicle Information', 'Make', 'make', 'Old make', 'New make'],
  ])(
    'saves %s through the shared draft workflow',
    async (entity_type, title, label, field, oldValue, newValue) => {
      const entity = {
        id: 9,
        entity_type,
        data: { [field]: oldValue, notes: '', imported: [{ keep: true }] },
      }
      await openNotes(entity)
      await button('Edit Entity').trigger('click')
      await tab(title)
      expect(input(label).element.value).toBe(oldValue)
      await input(label).setValue(newValue)
      entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
        id,
        ...payload,
      }))
      await button('Save Changes').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('edit').at(-1)[0]).toMatchObject({
        id: 9,
        entity_type,
        data: { [field]: newValue, imported: [{ keep: true }] },
      })
      expect(entity.data[field]).toBe(oldValue)
      await button('Edit Entity').trigger('click')
      expect(input(label).element.value).toBe(newValue)
    },
  )

  it('retains nested fields and sources after a failed form save for retry', async () => {
    await openNotes({ id: 9, entity_type: 'person', data: { address: { city: 'Old' }, notes: '' } })
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('New')
    await input('Source for City').setValue('New source')
    entityService.updateEntity.mockRejectedValueOnce(new Error('Unavailable'))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Unavailable')
    expect(input('City').element.value).toBe('New')
    expect(input('Source for City').element.value).toBe('New source')
    expect(wrapper.emitted('edit')).toBeUndefined()
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('edit').at(-1)[0].data).toMatchObject({
      address: { city: 'New' },
      sources: { 'address.city': 'New source' },
    })
    expect(wrapper.text()).toContain('View Mode')
  })

  it('includes silently refreshed notes when saving an existing field draft', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', address: { city: 'Old' }, notes: '<p>Initial</p>' },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('New')
    await wrapper.setProps({
      entity: { ...entity, data: { ...entity.data, notes: '<p>Refreshed</p>' } },
    })
    await tab('Notes')
    expect(textbox().text()).toBe('Refreshed')
    expect(entityService.updateEntity).not.toHaveBeenCalled()
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('edit').at(-1)[0].data).toMatchObject({
      address: { city: 'New' },
      notes: '<p>Refreshed</p>',
    })
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    expect(textbox().text()).toBe('Refreshed')
  })

  it('saves pending notes immediately on Cancel and preserves them when reopened', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    textbox().element.innerHTML = '<p>Pending notes</p>'
    await textbox().trigger('input')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))

    await button('Cancel').trigger('click')
    await flushPromises()

    expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Pending notes</p>' },
    })
    expect(textbox().attributes('contenteditable')).toBe('false')
    const saved = wrapper.emitted('edit').at(-1)[0]
    await vi.advanceTimersByTimeAsync(10000)
    wrapper.unmount()
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
    await openNotes(saved)
    expect(textbox().text()).toBe('Pending notes')
  })

  it('does not turn entering edit mode into a form edit or an autosave', async () => {
    await openNotes({ id: 9, entity_type: 'person', data: { first_name: 'Ada', notes: '' } })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    await vi.advanceTimersByTimeAsync(5000)
    expect(entityService.updateEntity).not.toHaveBeenCalled()
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({ notes: '' }),
    })
  })

  it('includes pending notes in the main form save before debounce and exits without a second write', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    textbox().element.innerHTML = '<p>Pending notes</p>'
    await textbox().trigger('input')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({ first_name: 'Ada', notes: '<p>Pending notes</p>' }),
    })
    const saved = wrapper.emitted('edit').at(-1)[0]
    await wrapper.setProps({ entity: saved })
    expect(textbox().attributes('contenteditable')).toBe('false')
    expect(textbox().text()).toBe('Pending notes')
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    vi.useRealTimers()
    await openNotes(saved)
    expect(textbox().text()).toBe('Pending notes')
  })

  it('holds autosave while the main form is saving, including on unmount', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    textbox().element.innerHTML = '<p>Pending notes</p>'
    await textbox().trigger('input')
    let completeSave
    entityService.updateEntity.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          completeSave = resolve
        }),
    )
    await button('Save Changes').trigger('click')
    await vi.advanceTimersByTimeAsync(10000)
    wrapper.unmount()
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    completeSave({ id: 9, ...entityService.updateEntity.mock.calls[0][2] })
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
  })

  it('orders an active autosave, the main form, and newer notes without losing fields or text', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: {
        first_name: 'Ada',
        notes: '<p>Initial</p>',
        address: { city: 'Old' },
        sources: { 'address.city': 'Old source' },
      },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    const completions = []
    entityService.updateEntity.mockImplementation(
      (_caseId, id, payload) =>
        new Promise((resolve) => {
          completions.push(async () => {
            const saved = { id, ...payload }
            resolve(saved)
            await flushPromises()
            await wrapper.setProps({ entity: saved })
          })
        }),
    )
    textbox().element.innerHTML = '<p>First</p>'
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(5000)
    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Basic Information')
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('input')
      .find((input) => input.element.value === 'Ada')
      .setValue('Grace')
    await tab('Address')
    await input('City').setValue('New')
    await input('Source for City').setValue('New source')
    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Notes')
      .trigger('click')
    await flushPromises()
    textbox().element.innerHTML = '<p>Main form notes</p>'
    await textbox().trigger('input')
    await button('Save Changes').trigger('click')
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    await completions[0]()
    expect(textbox().text()).toBe('Main form notes')
    expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
    textbox().element.innerHTML = '<p>Latest notes</p>'
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(5000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
    await completions[1]()
    expect(textbox().text()).toBe('Latest notes')
    expect(entityService.updateEntity).toHaveBeenCalledTimes(3)
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({
        first_name: 'Grace',
        notes: '<p>Latest notes</p>',
        address: { city: 'New' },
        sources: { 'address.city': 'New source' },
      }),
    })
    await completions[2]()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(3)
  })

  it.each(['immediate', 'delayed'])(
    'preserves submitted snapshots and later notes with %s parent acknowledgement',
    async (parentTiming) => {
      const entity = {
        id: 9,
        entity_type: 'person',
        data: {
          first_name: 'Ada',
          address: { city: 'Old', country: 'UK' },
          sources: { 'address.city': 'Old source' },
          notes: '<p>Initial</p>',
        },
      }
      await openNotes(entity)
      await button('Edit Entity').trigger('click')
      vi.useFakeTimers()
      const completions = []
      entityService.updateEntity.mockImplementation(
        (_caseId, id, payload) =>
          new Promise((resolve) => {
            completions.push(async () => {
              const saved = { id, ...payload }
              resolve(saved)
              await flushPromises()
              if (parentTiming === 'immediate') await wrapper.setProps({ entity: saved })
              return saved
            })
          }),
      )
      textbox().element.innerHTML = '<p>First</p>'
      await textbox().trigger('input')
      await vi.advanceTimersByTimeAsync(5000)
      await tab('Address')
      await input('City').setValue('Submitted city')
      await input('Source for City').setValue('Submitted source')
      await tab('Notes')
      textbox().element.innerHTML = '<p>Submitted notes</p>'
      await textbox().trigger('input')
      await button('Save Changes').trigger('click')

      // Mutate the live draft while the form snapshot waits behind the first note write.
      await tab('Address')
      await input('City').setValue('Later draft city')
      await input('Source for City').setValue('Later draft source')
      await tab('Notes')
      textbox().element.innerHTML = '<p>Notes while queued</p>'
      await textbox().trigger('input')
      await wrapper.setProps({ entity: JSON.parse(JSON.stringify(entity)) })
      const firstSaved = await completions[0]()
      expect(textbox().text()).toBe('Notes while queued')
      await tab('Address')
      expect(input('City').element.value).toBe('Later draft city')
      expect(input('Source for City').element.value).toBe('Later draft source')
      expect(entityService.updateEntity.mock.calls[0]).toEqual([
        7,
        9,
        { entity_type: 'person', data: { ...entity.data, notes: '<p>First</p>' } },
      ])
      expect(entityService.updateEntity.mock.calls[1]).toEqual([
        7,
        9,
        {
          entity_type: 'person',
          data: expect.objectContaining({
            address: { city: 'Submitted city', country: 'UK' },
            sources: { 'address.city': 'Submitted source' },
            notes: '<p>Submitted notes</p>',
          }),
        },
      ])
      await tab('Notes')
      expect(textbox().text()).toBe('Notes while queued')
      textbox().element.innerHTML = '<p>Latest notes</p>'
      await textbox().trigger('input')
      await vi.advanceTimersByTimeAsync(5000)
      expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
      const formSaved = await completions[1]()
      expect(textbox().text()).toBe('Latest notes')
      expect(entityService.updateEntity.mock.calls[2]).toEqual([
        7,
        9,
        {
          entity_type: 'person',
          data: { ...formSaved.data, notes: '<p>Latest notes</p>' },
        },
      ])
      const latestSaved = await completions[2]()
      expect(wrapper.emitted('edit')).toEqual([[firstSaved], [formSaved], [latestSaved]])

      // An older parent refresh must not roll back the workflow after the queue is idle.
      await wrapper.setProps({ entity: firstSaved })
      expect(textbox().text()).toBe('Latest notes')
      await button('Edit Entity').trigger('click')
      await tab('Address')
      expect(input('City').element.value).toBe('Submitted city')
      expect(input('Source for City').element.value).toBe('Submitted source')
      await tab('Notes')
      textbox().element.innerHTML = '<p>Next notes</p>'
      await textbox().trigger('input')
      await vi.advanceTimersByTimeAsync(5000)
      await button('Cancel').trigger('click')
      await wrapper.setProps({ entity: formSaved })
      expect(textbox().text()).toBe('Next notes')
      const nextSaved = await completions[3]()
      expect(nextSaved.data).toEqual({ ...formSaved.data, notes: '<p>Next notes</p>' })
      expect(wrapper.emitted('edit').at(-1)).toEqual([nextSaved])
      await vi.advanceTimersByTimeAsync(10000)
      wrapper.unmount()
      await flushPromises()
      expect(entityService.updateEntity).toHaveBeenCalledTimes(4)
      expect(entity.data.address.city).toBe('Old')
    },
  )

  it('accepts a newer saved Entity when the mounted dialog is reopened and preserves it in autosave', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      updated_at: '2026-09-06T01:00:00Z',
      data: { address: { city: 'Old' }, notes: '<p>Initial</p>' },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
      updated_at: '2026-09-06T01:01:00Z',
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    const locallySaved = wrapper.emitted('edit').at(-1)[0]
    await button('Close').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
    await wrapper.setProps({ show: false })
    const refreshed = {
      ...entity,
      updated_at: '2026-09-06T01:02:00Z',
      data: {
        address: { city: 'Refreshed city' },
        sources: { 'address.city': 'Refreshed source' },
        notes: '<p>Refreshed notes</p>',
      },
    }
    await wrapper.setProps({ show: true, entity: refreshed })
    expect(textbox().text()).toBe('Refreshed notes')
    await button('Edit Entity').trigger('click')
    await tab('Address')
    expect(input('City').element.value).toBe('Refreshed city')
    expect(input('Source for City').element.value).toBe('Refreshed source')
    await wrapper.setProps({ entity: locallySaved })
    await tab('Notes')
    expect(textbox().text()).toBe('Refreshed notes')
    vi.useFakeTimers()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    textbox().element.innerHTML = '<p>New notes after reopening</p>'
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(5000)
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: { ...refreshed.data, notes: '<p>New notes after reopening</p>' },
    })
    expect(wrapper.emitted('edit').at(-1)[0].data).toEqual({
      ...refreshed.data,
      notes: '<p>New notes after reopening</p>',
    })
  })

  it('keeps the dialog open when Close fails to save and retries on Close', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    entityService.updateEntity.mockRejectedValue(new Error('Unavailable'))
    textbox().element.innerHTML = '<p>Unsaved notes</p>'
    await textbox().trigger('input')
    await button('Cancel').trigger('click')
    await flushPromises()
    await button('Close').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(textbox().text()).toBe('Unsaved notes')
    expect(wrapper.text()).toContain('Failed to save notes')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Close').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(3)
  })

  it('shares an active Cancel save across repeated Close requests and reports one close', async () => {
    await openNotes({ id: 9, entity_type: 'person', data: { notes: '<p>Initial</p>' } })
    await button('Edit Entity').trigger('click')
    vi.useFakeTimers()
    let completeSave
    entityService.updateEntity.mockImplementationOnce(
      (_caseId, id, payload) =>
        new Promise((resolve) => {
          completeSave = () => resolve({ id, ...payload })
        }),
    )
    textbox().element.innerHTML = '<p>Pending <strong>notes</strong></p>'
    await textbox().trigger('input')
    await button('Cancel').trigger('click')
    await button('Close').trigger('click')
    await button('Close').trigger('click')
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    completeSave()
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(textbox().get('strong').text()).toBe('notes')
    await wrapper.setProps({ show: false })
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
  })

  it('flushes pending notes when the parent hides the mounted dialog', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    textbox().element.innerHTML = '<p>Pending notes</p>'
    await textbox().trigger('input')
    await wrapper.setProps({ show: false })
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Pending notes</p>' },
    })
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['hide', 'debounce'],
    ['hide', 'active'],
    ['hide', 'newer'],
    ['unmount', 'debounce'],
    ['unmount', 'active'],
    ['unmount', 'newer'],
  ])('captures notes on %s with %s work without duplicate writes', async (exit, pending) => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: {
        address: { city: 'Saved' },
        sources: { 'address.city': 'Saved source' },
        notes: '<p>Initial</p>',
      },
    }
    await openNotes(entity)
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('Unsubmitted')
    await input('Source for City').setValue('Unsubmitted source')
    await tab('Notes')
    vi.useFakeTimers()
    const writes = deferSaves()
    await typeNotes('<p>Captured <em>notes</em></p>')
    if (pending !== 'debounce') await vi.advanceTimersByTimeAsync(5000)
    if (pending === 'newer') await typeNotes('<p>Newer <strong>notes</strong></p>')
    if (exit === 'hide') await wrapper.setProps({ show: false })
    wrapper.unmount()
    expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
    writes[0].succeed()
    await flushPromises()
    if (pending === 'newer') {
      expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
      writes[1].succeed()
      await flushPromises()
    }
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(pending === 'newer' ? 2 : 1)
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: {
        ...entity.data,
        notes:
          pending === 'newer'
            ? '<p>Newer <strong>notes</strong></p>'
            : '<p>Captured <em>notes</em></p>',
      },
    })
  })

  it.each(['notes', 'form'])(
    'does not retry a failed active %s save in a teardown loop',
    async (kind) => {
      await openNotes({ id: 9, entity_type: 'person', data: { notes: '<p>Initial</p>' } })
      await button('Edit Entity').trigger('click')
      vi.useFakeTimers()
      const writes = deferSaves()
      await typeNotes('<p>Pending notes</p>')
      if (kind === 'form') await button('Save Changes').trigger('click')
      else await vi.advanceTimersByTimeAsync(5000)
      await wrapper.setProps({ show: false })
      wrapper.unmount()
      writes[0].fail()
      await flushPromises()
      await vi.advanceTimersByTimeAsync(20000)
      expect(entityService.updateEntity).toHaveBeenCalledTimes(1)
      expect(wrapper.emitted('edit')).toBeUndefined()
    },
  )

  it('ignores Escape while form saving, then cancels editing and retries failed notes before closing', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { address: { city: 'Old' }, notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('Draft')
    await tab('Notes')
    vi.useFakeTimers()
    const writes = deferSaves()
    await typeNotes('<p>Pending notes</p>')
    await button('Save Changes').trigger('click')
    await textbox().trigger('keydown', { key: 'Escape' })
    expect(textbox().attributes('contenteditable')).toBe('true')
    expect(wrapper.emitted('close')).toBeUndefined()
    writes[0].fail()
    await flushPromises()
    expect(wrapper.text()).toContain('Unavailable')
    await textbox().trigger('keydown', { key: 'Escape' })
    expect(textbox().attributes('contenteditable')).toBe('false')
    writes[1].fail()
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to save notes')
    await textbox().trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toBeUndefined()
    writes[2].fail()
    await flushPromises()
    expect(textbox().text()).toBe('Pending notes')
    expect(wrapper.emitted('close')).toBeUndefined()
    await textbox().trigger('keydown', { key: 'Escape' })
    writes[3].succeed()
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('Failed to save notes')
    expect(entityService.updateEntity.mock.calls[3][2].data.address.city).toBe('Old')
  })

  it('includes failed Cancel notes when edit mode is reopened and Save Changes retries', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: {
        first_name: 'Ada',
        notes: '<p>Initial</p>',
        address: { city: 'Old' },
        sources: { 'address.city': 'Old source' },
      },
    })
    await button('Edit Entity').trigger('click')
    await tab('Address')
    await input('City').setValue('Discarded city')
    await input('Source for City').setValue('Discarded source')
    await tab('Notes')
    await flushPromises()
    vi.useFakeTimers()
    entityService.updateEntity.mockRejectedValueOnce(new Error('Unavailable'))
    textbox().element.innerHTML = '<p>Unsaved notes</p>'
    await textbox().trigger('input')
    await button('Cancel').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to save notes')
    expect(textbox().attributes('contenteditable')).toBe('false')
    await button('Edit Entity').trigger('click')
    await tab('Address')
    expect(input('City').element.value).toBe('Old')
    expect(input('Source for City').element.value).toBe('Old source')
    await tab('Notes')
    expect(wrapper.text()).toContain('Retry with Save Changes')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({
        notes: '<p>Unsaved notes</p>',
        address: { city: 'Old' },
        sources: { 'address.city': 'Old source' },
      }),
    })
    expect(textbox().text()).toBe('Unsaved notes')
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(2)
  })

  it('loads and refreshes silently, saves edits through the service and form, and reopens HTML', async () => {
    const entity = {
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial notes</p>' },
    }
    await openNotes(entity)
    expect(textbox().text()).toBe('Initial notes')
    expect(textbox().attributes('contenteditable')).toBe('false')
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    // Entering edit mode is not a user edit.
    await vi.advanceTimersByTimeAsync(5100)
    expect(entityService.updateEntity).not.toHaveBeenCalled()

    for (const notes of ['<p>Refreshed notes</p>', '']) {
      await wrapper.setProps({ entity: { ...entity, data: { ...entity.data, notes } } })
      expect(textbox().text()).toBe(notes ? 'Refreshed notes' : '')
      await vi.advanceTimersByTimeAsync(5100)
      expect(entityService.updateEntity).not.toHaveBeenCalled()
      expect(wrapper.emitted('edit')).toBeUndefined()
    }

    const saved = '<p>Saved <em>entity</em> notes</p>'
    const savedEntity = { ...entity, data: { ...entity.data, notes: saved } }
    entityService.updateEntity.mockResolvedValue(savedEntity)
    textbox().element.innerHTML = saved
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(5100)
    expect(entityService.updateEntity).toHaveBeenCalledExactlyOnceWith(7, 9, {
      entity_type: 'person',
      data: savedEntity.data,
    })
    expect(wrapper.emitted('edit').at(-1)).toEqual([savedEntity])

    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({ notes: saved }),
    })
    wrapper.unmount()
    vi.useRealTimers()
    await openNotes(savedEntity)
    expect(textbox().get('em').text()).toBe('entity')
    expect(textbox().text()).toBe('Saved entity notes')
  })
})
