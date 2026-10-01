import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NoteEditor from '../NoteEditor.vue'

let wrapper
let warningSpy

beforeEach(() => {
  warningSpy = vi.spyOn(console, 'warn')
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  wrapper?.unmount()
  expect(warningSpy.mock.calls.flat().join(' ')).not.toContain('Duplicate extension names')
  warningSpy.mockRestore()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const mountNotes = (props) =>
  mount(NoteEditor, {
    props,
    attachTo: document.body,
    global: { plugins: [createVuetify({ components, directives, theme: false })] },
  })
const textbox = () => wrapper.get('[role="textbox"][aria-label="Case notes"]')

describe('Case note editor', () => {
  it('changes edit mode silently and emits subsequent user edits', async () => {
    wrapper = mountNotes({ modelValue: '<p>Initial notes</p>', isEditing: false })
    await flushPromises()
    expect(textbox().attributes('contenteditable')).toBe('false')
    await wrapper.setProps({ isEditing: true })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    textbox().element.innerHTML = '<p>User edit</p>'
    await textbox().trigger('input')
    expect(wrapper.emitted('update:modelValue')).toEqual([['<p>User edit</p>']])
    await wrapper.setProps({ isEditing: false })
    expect(textbox().attributes('contenteditable')).toBe('false')
    expect(wrapper.emitted('update:modelValue')).toHaveLength(1)
  })

  it('emits each edit once, immediately', async () => {
    wrapper = mountNotes({ modelValue: '<p>Initial</p>' })
    await flushPromises()
    vi.useFakeTimers()
    textbox().element.innerHTML = '<p>Manual edit</p>'
    await textbox().trigger('input')
    expect(wrapper.emitted('update:modelValue')).toEqual([['<p>Manual edit</p>']])
    await vi.advanceTimersByTimeAsync(5000)
    expect(wrapper.emitted('update:modelValue')).toHaveLength(1)
  })

  it('loads and replaces notes silently, then reopens emitted HTML', async () => {
    wrapper = mountNotes({ modelValue: '<p>Initial notes</p>' })
    await flushPromises()
    expect(textbox().text()).toBe('Initial notes')

    for (const content of ['<p>Refreshed notes</p>', '']) {
      await wrapper.setProps({ modelValue: content })
      expect(textbox().text()).toBe(content ? 'Refreshed notes' : '')
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    }

    textbox().element.innerHTML = '<p>Saved <strong>case</strong> notes</p>'
    await textbox().trigger('input')
    const saved = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(saved).toBe('<p>Saved <strong>case</strong> notes</p>')
    wrapper.unmount()
    wrapper = mountNotes({ modelValue: saved })
    await flushPromises()
    expect(textbox().get('strong').text()).toBe('case')
    expect(textbox().text()).toBe('Saved case notes')
  })

  it('labels formatting controls without a save status', async () => {
    wrapper = mountNotes({ modelValue: '<p>Initial notes</p>' })
    await flushPromises()
    expect(wrapper.get('[aria-label="Bold (Ctrl+B)"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('[role="status"]').text()).toBe('')
  })
})
