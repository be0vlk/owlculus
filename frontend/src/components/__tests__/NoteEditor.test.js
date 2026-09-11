import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NoteEditor from '../NoteEditor.vue'
import { caseService } from '@/services/case'

vi.mock('@/services/case', () => ({ caseService: { updateCase: vi.fn() } }))
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
})

afterEach(() => {
  wrapper?.unmount()
  expect(warningSpy.mock.calls.flat().join(' ')).not.toContain('Duplicate extension names')
  warningSpy.mockRestore()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Case note editor', () => {
  it('changes edit mode silently and still saves subsequent user edits', async () => {
    wrapper = mount(NoteEditor, {
      props: { modelValue: '<p>Initial notes</p>', caseId: 7, isEditing: false },
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await flushPromises()
    vi.useFakeTimers()
    await wrapper.setProps({ isEditing: true })
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(caseService.updateCase).not.toHaveBeenCalled()
    const box = wrapper.get('[aria-label="Case notes"]')
    box.element.innerHTML = '<p>User edit</p>'
    await box.trigger('input')
    await vi.advanceTimersByTimeAsync(1000)
    expect(caseService.updateCase).toHaveBeenCalledExactlyOnceWith(7, { notes: '<p>User edit</p>' })
    await wrapper.setProps({ isEditing: false })
    expect(box.attributes('contenteditable')).toBe('false')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.emitted('update:modelValue')).toEqual([['<p>User edit</p>']])
    expect(caseService.updateCase).toHaveBeenCalledTimes(1)
  })

  it('emits manual edits immediately without saving on timers or unmount', async () => {
    wrapper = mount(NoteEditor, {
      props: { modelValue: '<p>Initial</p>', caseId: 7, saveMode: 'manual' },
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await flushPromises()
    vi.useFakeTimers()
    const box = wrapper.get('[aria-label="Case notes"]')
    box.element.innerHTML = '<p>Manual edit</p>'
    await box.trigger('input')
    expect(wrapper.emitted('update:modelValue')).toEqual([['<p>Manual edit</p>']])
    await vi.advanceTimersByTimeAsync(5000)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(5000)
    expect(caseService.updateCase).not.toHaveBeenCalled()
  })

  it('loads and replaces notes silently, then saves a user edit and reopens the HTML', async () => {
    const mountNotes = (modelValue) =>
      mount(NoteEditor, {
        props: { modelValue, caseId: 7 },
        attachTo: document.body,
        global: { plugins: [createVuetify({ components, directives, theme: false })] },
      })
    wrapper = mountNotes('<p>Initial notes</p>')
    await flushPromises()
    vi.useFakeTimers()
    const textbox = () => wrapper.get('[role="textbox"][aria-label="Case notes"]')
    expect(textbox().text()).toBe('Initial notes')
    await vi.advanceTimersByTimeAsync(1100)
    expect(caseService.updateCase).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    for (const content of ['<p>Refreshed notes</p>', '']) {
      await wrapper.setProps({ modelValue: content })
      expect(textbox().text()).toBe(content ? 'Refreshed notes' : '')
      await vi.advanceTimersByTimeAsync(1100)
      expect(caseService.updateCase).not.toHaveBeenCalled()
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    }

    caseService.updateCase.mockResolvedValue({})
    textbox().element.innerHTML = '<p>Saved <strong>case</strong> notes</p>'
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(1100)
    const saved = '<p>Saved <strong>case</strong> notes</p>'
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([saved])
    expect(caseService.updateCase).toHaveBeenCalledExactlyOnceWith(7, { notes: saved })
    wrapper.unmount()
    vi.useRealTimers()
    wrapper = mountNotes(saved)
    await flushPromises()
    expect(textbox().get('strong').text()).toBe('case')
    expect(textbox().text()).toBe('Saved case notes')
  })

  it('labels formatting and editing, and reports failed saves followed by recovery', async () => {
    wrapper = mount(NoteEditor, {
      props: { modelValue: '<p>Initial notes</p>', caseId: 7 },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await flushPromises()
    expect(wrapper.get('[aria-label="Bold (Ctrl+B)"]').attributes('aria-pressed')).toBe('false')
    const textbox = wrapper.get('[role="textbox"][aria-label="Case notes"]')
    vi.useFakeTimers()
    caseService.updateCase.mockRejectedValueOnce(new Error('Unavailable'))
    textbox.element.innerHTML = '<p>New notes</p>'
    await textbox.trigger('input')
    await vi.advanceTimersByTimeAsync(1100)
    expect(wrapper.get('[role="alert"]').text()).toContain('Failed to save notes')
    caseService.updateCase.mockResolvedValueOnce({})
    textbox.element.innerHTML = '<p>Recovered notes</p>'
    await textbox.trigger('input')
    await vi.advanceTimersByTimeAsync(1100)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('[role="status"]').text()).toContain('Last saved:')
  })
})
