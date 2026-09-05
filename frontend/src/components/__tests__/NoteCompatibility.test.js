import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import NoteEditor from '../NoteEditor.vue'
import EntityDetailsModal from '../entities/EntityDetailsModal.vue'
import { caseService } from '@/services/case'
import { entityService } from '@/services/entity'
import { richNote } from './fixtures/richNote'

vi.mock('@/services/case', () => ({ caseService: { updateCase: vi.fn() } }))
vi.mock('@/services/entity', () => ({ entityService: { updateEntity: vi.fn() } }))
let wrapper
let warningSpy
const entity = { id: 9, entity_type: 'person', data: { first_name: 'Ada' } }
const textbox = () => wrapper.get('[role="textbox"][aria-multiline="true"]')
const control = (label) => wrapper.get(`[aria-label="${label}"]`)

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
  // jsdom has no layout; ProseMirror scrolls selections after toolbar actions.
  Range.prototype.getClientRects = () => []
  Range.prototype.getBoundingClientRect = () => new DOMRect()
  caseService.updateCase.mockResolvedValue({})
  entityService.updateEntity.mockImplementation(async (_caseId, _id, data) => ({ id: 9, ...data }))
})
afterEach(() => {
  wrapper?.unmount()
  expect(warningSpy.mock.calls.flat().join(' ')).not.toContain('Duplicate extension names')
  warningSpy.mockRestore()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  delete Range.prototype.getClientRects
  delete Range.prototype.getBoundingClientRect
  document.body.innerHTML = ''
})

async function open(kind, notes, editable = true) {
  wrapper = mount(kind === 'case' ? NoteEditor : EntityDetailsModal, {
    props:
      kind === 'case'
        ? { modelValue: notes, caseId: 7, isEditing: editable }
        : {
            show: true,
            entity: { ...entity, data: { ...entity.data, notes } },
            caseId: 7,
            existingEntities: [],
          },
    attachTo: document.body,
    global: {
      plugins: [createVuetify({ components, directives, theme: false })],
      // Keep the real editor and toolbar; browser smoke covers dialog focus/portals.
      stubs: {
        VDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' },
      },
    },
  })
  await flushPromises()
  if (kind === 'entity') {
    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Notes')
      .trigger('click')
    if (editable)
      await wrapper
        .findAll('button')
        .find((button) => button.text() === 'Edit Entity')
        .trigger('click')
    await flushPromises()
  }
}

function expectRichContent() {
  const box = textbox()
  for (const [selector, text] of Object.entries({
    h1: 'Investigation',
    h2: 'Evidence',
    h3: 'Sources',
    h4: 'Detail',
    h5: 'Reference',
    h6: 'Appendix',
    strong: 'Bold',
    em: 'Italic',
    u: 'Underline',
    s: 'Strike',
    'ul:not([data-type]) > li': 'Bullet',
    'ol[start="3"] > li': 'Third',
    blockquote: 'Witness statement',
    'pre > code.language-js': 'const evidence = 1;',
    'p > code': 'inline()',
  }))
    expect(box.get(selector).text()).toBe(text)
  expect(box.get('a').attributes('href')).toBe('https://example.org/evidence')
  expect(box.get('a').attributes('target')).toBe('_blank')
  for (const [color, text, background] of [
    ['#ffe066', 'Yellow', 'rgb(255, 224, 102)'],
    ['#74c0fc', 'Blue', 'rgb(116, 192, 252)'],
  ]) {
    expect(box.get(`mark[data-color="${color}"]`).text()).toBe(text)
    expect(box.get(`mark[data-color="${color}"]`).element.style.backgroundColor).toBe(background)
  }
  const tasks = box.findAll('li.task-item')
  expect(tasks.map((task) => task.attributes('data-checked'))).toEqual(['true', 'false', 'false'])
  expect(tasks.map((task) => task.get('input').element.checked)).toEqual([true, false, false])
  expect(tasks[0].get(':scope > div > ul[data-type="taskList"] > li > div > p').text()).toBe(
    'Follow up',
  )
}

describe.each(['case', 'entity'])('%s note compatibility', (kind) => {
  it('preserves supported rich HTML through editing, saving and reopening', async () => {
    await open(kind, richNote)
    expectRichContent()
    vi.useFakeTimers()
    textbox().element.lastElementChild.textContent = 'Edited end of note'
    await textbox().trigger('input')
    await vi.advanceTimersByTimeAsync(5100)
    const saved =
      kind === 'case'
        ? caseService.updateCase.mock.calls.at(-1)[1].notes
        : entityService.updateEntity.mock.calls.at(-1)[2].data.notes
    expect(saved).toContain('Edited end of note')
    wrapper.unmount()
    vi.useRealTimers()
    await open(kind, saved)
    expectRichContent()
    expect(textbox().text()).toContain('Edited end of note')
  })

  it.each([
    ['Bold (Ctrl+B)', 'strong'],
    ['Italic (Ctrl+I)', 'em'],
    ['Underline (Ctrl+U)', 'u'],
    ['Strikethrough', 's'],
    ['Highlight', 'mark'],
    ['Bullet List', 'ul > li'],
    ['Ordered List', 'ol > li'],
    ['Task List', 'ul[data-type="taskList"] > li > div > p'],
    ['Blockquote', 'blockquote'],
  ])('applies %s and exposes its pressed state', async (label, selector) => {
    await open(kind, '<p>Selected text</p>')
    const range = document.createRange()
    range.selectNodeContents(textbox().get('p').element)
    textbox().element.focus()
    window.getSelection().removeAllRanges()
    window.getSelection().addRange(range)
    document.dispatchEvent(new Event('selectionchange'))
    await flushPromises()
    expect(control(label).attributes('aria-pressed')).toBe('false')
    await control(label).trigger('click')
    await flushPromises()
    expect(textbox().get(selector).text()).toBe('Selected text')
    await vi.waitFor(() => expect(control(label).attributes('aria-pressed')).toBe('true'))
    expect(control(label).classes()).toContain('v-btn--variant-tonal')
    await control(label).trigger('click')
    await vi.waitFor(() => expect(control(label).attributes('aria-pressed')).toBe('false'))
  })

  it('keeps readonly content and controls non-editable in both views', async () => {
    await open(kind, richNote, false)
    for (const fullscreen of [false, true]) {
      if (fullscreen) {
        await control('Expand to fullscreen').trigger('click')
        await flushPromises()
      }
      expect(textbox().attributes('contenteditable')).toBe('false')
      for (const button of wrapper.findAll('[aria-pressed]'))
        expect(button.element.disabled).toBe(true)
      await textbox().get('input[type="checkbox"]').setValue(false)
      expect(textbox().get('li.task-item').attributes('data-checked')).toBe('true')
      expectRichContent()
    }
    expect(caseService.updateCase).not.toHaveBeenCalled()
    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it('retains empty and heading placeholders after clearing', async () => {
    await open(kind, '')
    expect(textbox().get('p.is-editor-empty').attributes('data-placeholder')).toBeTruthy()
    wrapper.unmount()
    await open(kind, '<h2></h2>')
    expect(textbox().get('h2.is-empty').attributes('data-placeholder')).toBe("What's the title?")
    textbox().element.innerHTML = '<p>New note</p>'
    await textbox().trigger('input')
    await flushPromises()
    expect(textbox().find('.is-editor-empty').exists()).toBe(false)
    textbox().element.innerHTML = '<p></p>'
    await textbox().trigger('input')
    await flushPromises()
    expect(textbox().get('p.is-editor-empty').attributes('data-placeholder')).toBeTruthy()
  })

  it('edits fullscreen and returns the same content to the embedded editor', async () => {
    await open(kind, richNote)
    control('Expand to fullscreen').element.focus()
    await control('Expand to fullscreen').trigger('click')
    await flushPromises()
    expectRichContent()
    textbox().element.lastElementChild.textContent = 'Fullscreen edit'
    await textbox().trigger('input')
    await flushPromises()
    await control('Close notes').trigger('click')
    await flushPromises()
    expectRichContent()
    expect(document.activeElement).toBe(control('Expand to fullscreen').element)
    expect(textbox().text()).toContain('Fullscreen edit')
    textbox().element.lastElementChild.textContent = 'Embedded edit'
    await textbox().trigger('input')
    await flushPromises()
    expect(textbox().text()).toContain('Embedded edit')
  })
})
