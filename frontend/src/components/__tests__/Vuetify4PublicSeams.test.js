import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApiKeyManagementCard from '../ApiKeyManagementCard.vue'
import NewInviteModal from '../NewInviteModal.vue'
import SystemConfigurationCard from '../SystemConfigurationCard.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))

const PassthroughStub = { template: '<div><slot /></div>' }
const SelectStub = {
  props: { items: { type: Array, default: () => [] } },
  template:
    '<div data-testid="select-item"><slot name="item" :props="{}" :item="items[0]" /></div>',
}
const ListItemStub = {
  template:
    '<div><slot name="prepend" /><slot name="title" /><slot name="subtitle" /><slot /></div>',
}
const IconStub = {
  props: { icon: String, color: String },
  template: '<span>{{ icon }} {{ color }}</span>',
}
const TextFieldStub = {
  props: { modelValue: String, label: String },
  emits: ['update:modelValue'],
  template:
    '<input :aria-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

const vuetifyStubs = {
  VAlert: PassthroughStub,
  VBtn: PassthroughStub,
  VCard: PassthroughStub,
  VCardActions: PassthroughStub,
  VCardText: PassthroughStub,
  VCardTitle: PassthroughStub,
  VChip: PassthroughStub,
  VCol: PassthroughStub,
  VContainer: PassthroughStub,
  VDialog: PassthroughStub,
  VDivider: PassthroughStub,
  VForm: PassthroughStub,
  VIcon: IconStub,
  VListItem: ListItemStub,
  VListItemSubtitle: PassthroughStub,
  VListItemTitle: PassthroughStub,
  VProgressLinear: PassthroughStub,
  VRow: PassthroughStub,
  VSelect: SelectStub,
  VSkeletonLoader: PassthroughStub,
  VSpacer: PassthroughStub,
  VTable: PassthroughStub,
  VTextField: TextFieldStub,
  VTooltip: PassthroughStub,
}

describe('Vuetify 4 public component seams', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders role metadata from the Vuetify 4 select item payload', () => {
    const wrapper = shallowMount(NewInviteModal, {
      props: { show: true },
      global: { stubs: vuetifyStubs },
    })

    expect(wrapper.get('[data-testid="select-item"]').text()).toContain('Analyst')
    expect(wrapper.get('[data-testid="select-item"]').text()).toContain(
      'Read-only access to assigned cases',
    )
    expect(wrapper.get('[data-testid="select-item"]').text()).toContain('mdi-chart-line info')
  })

  it('renders provider icons from the Vuetify 4 select item payload', async () => {
    api.get.mockResolvedValue({ data: {} })
    const wrapper = shallowMount(ApiKeyManagementCard, {
      global: { stubs: vuetifyStubs },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="select-item"]').text()).toContain('mdi-robot')
  })

  it('handles the Vuetify 4 model update event for the case-number prefix', async () => {
    api.get.mockImplementation(async (url) => ({
      data:
        url === '/api/admin/configuration'
          ? { case_number_template: 'PREFIX-YYMM-NN', case_number_prefix: 'CASE' }
          : { example_case_number: 'CASE-2609-01' },
    }))

    const wrapper = shallowMount(SystemConfigurationCard, {
      global: { stubs: vuetifyStubs },
    })
    await flushPromises()
    await wrapper.get('input[aria-label="Prefix (2-8 letters/numbers)"]').setValue('INV')

    expect(api.get).toHaveBeenLastCalledWith(
      '/api/admin/configuration/preview?template=PREFIX-YYMM-NN&prefix=INV',
    )
  })
})
