import { afterEach, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

const wrappers = []

beforeEach(() => {
  vi.stubGlobal('visualViewport', new EventTarget())
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
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

export function mountWithVuetify(component, options = {}) {
  const wrapper = mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [
        ...(options.global?.plugins || []),
        createVuetify({ components, directives, theme: false }),
      ],
    },
  })
  wrappers.push(wrapper)
  return wrapper
}
