import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import ConfirmationDialog from '../ConfirmationDialog.vue'

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

it('renders caller text as text, never as markup', async () => {
  vi.stubGlobal('visualViewport', new EventTarget())
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  const wrapper = mount(ConfirmationDialog, {
    attachTo: document.body,
    global: { plugins: [createVuetify({ components, directives, theme: false })] },
  })
  wrapper.vm.confirmDelete('task "<img src=x>"').catch(() => {})
  await flushPromises()
  const dialog = document.querySelector('[role="dialog"][aria-label="Confirm Deletion"]')
  expect(dialog.textContent).toContain('delete task "<img src=x>"?')
  expect(dialog.querySelector('img')).toBeNull()
  wrapper.unmount()
})
