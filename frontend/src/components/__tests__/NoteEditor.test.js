import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NoteEditor from '../NoteEditor.vue'
import { caseService } from '@/services/case'

vi.mock('@/services/case', () => ({ caseService: { updateCase: vi.fn() } }))
let wrapper

afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  document.body.innerHTML = ''
})

describe('Case note editor', () => {
  it('labels formatting and editing, and reports failed saves followed by recovery', async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
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
