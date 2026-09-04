import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CaseTabs from '../CaseTabs.vue'

const TabsStub = defineComponent({
  props: { modelValue: String },
  emits: ['update:modelValue'],
  template:
    '<div><button data-testid="select-evidence" @click="$emit(\'update:modelValue\', \'evidence\')">Evidence</button><slot /></div>',
})
const TabStub = defineComponent({ template: '<button><slot /></button>' })
const WindowStub = defineComponent({ template: '<div><slot /></div>' })
const WindowItemStub = defineComponent({ template: '<div><slot /></div>' })
const ContainerStub = defineComponent({ template: '<div><slot /></div>' })

const tabs = [
  { name: 'entities', label: 'Entities' },
  { name: 'evidence', label: 'Evidence' },
]

describe('CaseTabs navigation', () => {
  it('renders the requested tab and reports user tab changes', async () => {
    const wrapper = mount(CaseTabs, {
      props: { tabs, modelValue: 'evidence' },
      global: {
        stubs: {
          VTabs: TabsStub,
          VTab: TabStub,
          VWindow: WindowStub,
          VWindowItem: WindowItemStub,
          VContainer: ContainerStub,
        },
      },
    })

    expect(wrapper.findComponent(TabsStub).props('modelValue')).toBe('evidence')

    await wrapper.get('[data-testid="select-evidence"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['evidence']])
  })

  it('falls back to the first available tab when the requested tab is unavailable', () => {
    const wrapper = mount(CaseTabs, {
      props: { tabs, modelValue: 'admin-only' },
      global: {
        stubs: {
          VTabs: TabsStub,
          VTab: TabStub,
          VWindow: WindowStub,
          VWindowItem: WindowItemStub,
          VContainer: ContainerStub,
        },
      },
    })

    expect(wrapper.findComponent(TabsStub).props('modelValue')).toBe('entities')
  })
})
