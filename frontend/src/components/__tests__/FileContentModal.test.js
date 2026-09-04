import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import FileContentModal from '../FileContentModal.vue'
import { evidenceService } from '@/services/evidence'

vi.mock('@/services/evidence', () => ({ evidenceService: { getEvidenceContent: vi.fn() } }))
let wrapper

afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('Evidence preview', () => {
  it('announces loading, displays content, and closes through its named action', async () => {
    vi.stubGlobal('visualViewport', new EventTarget())
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
    let finish
    evidenceService.getEvidenceContent.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    wrapper = mount(FileContentModal, {
      props: { modelValue: true, evidenceItem: { id: 2, title: 'statement.txt' } },
      attachTo: document.body,
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await flushPromises()
    const dialog = document.querySelector(
      '[role="dialog"][aria-label="Text File Content: statement.txt"]',
    )
    expect(dialog).not.toBeNull()
    expect(dialog.querySelector('[aria-label="Loading file preview"]')).not.toBeNull()
    finish({
      content: 'Witness statement',
      file_info: { filename: 'statement.txt', file_size: 17 },
    })
    await flushPromises()
    expect(dialog.textContent).toContain('Witness statement')
    expect(dialog.querySelector('[aria-label="Loading file preview"]')).toBeNull()
    dialog.querySelector('[aria-label="Close file preview"]').click()
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })
})
