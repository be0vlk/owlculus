import { afterEach, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { defaults } from '@/plugins/vuetify'

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

export const createTestVuetify = () =>
  createVuetify({ components, directives, defaults, theme: false })

export function mountWithVuetify(component, options = {}) {
  const wrapper = mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [...(options.global?.plugins || []), createTestVuetify()],
    },
  })
  wrappers.push(wrapper)
  return wrapper
}
