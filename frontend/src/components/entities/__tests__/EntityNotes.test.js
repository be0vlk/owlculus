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

describe('Entity notes with the real editor', () => {
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
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
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
      data: expect.objectContaining({ first_name: 'Grace', notes: '<p>Latest notes</p>' }),
    })
    await completions[2]()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(entityService.updateEntity).toHaveBeenCalledTimes(3)
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

  it('includes failed Cancel notes when edit mode is reopened and Save Changes retries', async () => {
    await openNotes({
      id: 9,
      entity_type: 'person',
      data: { first_name: 'Ada', notes: '<p>Initial</p>' },
    })
    await button('Edit Entity').trigger('click')
    await flushPromises()
    vi.useFakeTimers()
    entityService.updateEntity.mockRejectedValueOnce(new Error('Unavailable'))
    textbox().element.innerHTML = '<p>Unsaved notes</p>'
    await textbox().trigger('input')
    await button('Cancel').trigger('click')
    await flushPromises()
    await button('Edit Entity').trigger('click')
    entityService.updateEntity.mockImplementation(async (_caseId, id, payload) => ({
      id,
      ...payload,
    }))
    await button('Save Changes').trigger('click')
    await flushPromises()
    expect(entityService.updateEntity).toHaveBeenLastCalledWith(7, 9, {
      entity_type: 'person',
      data: expect.objectContaining({ notes: '<p>Unsaved notes</p>' }),
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
