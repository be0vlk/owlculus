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

describe('Entity notes with the real editor', () => {
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
