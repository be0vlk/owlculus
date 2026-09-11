import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, DOMWrapper } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import RenameDialog from '../RenameDialog.vue'
import { evidenceService } from '@/services/evidence'

vi.mock('@/services/evidence', () => ({ evidenceService: { updateFolder: vi.fn() } }))
let wrapper

afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

it('validates keyboard submissions before renaming evidence', async () => {
  vi.stubGlobal('visualViewport', new EventTarget())
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  wrapper = mount(RenameDialog, {
    props: { modelValue: false, item: { id: 1, title: 'Documents', is_folder: true } },
    attachTo: document.body,
    global: { plugins: [createVuetify({ components, directives, theme: false })] },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(
    document.querySelector('[role="dialog"][aria-label="Rename evidence"]'),
  )
  await dialog.get('input').setValue('Invalid/name')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(dialog.text()).toContain('Name can only contain')
  expect(evidenceService.updateFolder).not.toHaveBeenCalled()
  evidenceService.updateFolder.mockResolvedValue({ id: 1, title: 'Archive', is_folder: true })
  await dialog.get('input').setValue('Archive')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('renamed')).toEqual([[{ id: 1, title: 'Archive', is_folder: true }]])
})
