import { computed, ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApiKeyManagementCard from '../ApiKeyManagementCard.vue'
import NewInviteModal from '../NewInviteModal.vue'
import SystemConfigurationCard from '../SystemConfigurationCard.vue'
import { useApiKeys } from '@/composables/useApiKeys'
import { useSystemConfiguration } from '@/composables/useSystemConfiguration'

vi.mock('@/composables/useApiKeys', () => ({ useApiKeys: vi.fn() }))
vi.mock('@/composables/useSystemConfiguration', () => ({ useSystemConfiguration: vi.fn() }))

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
  VRow: PassthroughStub,
  VSelect: SelectStub,
  VSpacer: PassthroughStub,
  VTable: PassthroughStub,
  VTextField: TextFieldStub,
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
    useApiKeys.mockReturnValue({
      loading: ref(false),
      saving: ref(false),
      deleting: ref(false),
      error: ref(null),
      showAddDialog: ref(true),
      showEditDialog: ref(false),
      editingProvider: ref(null),
      newKeyForm: ref({ provider: '', name: '', api_key: '' }),
      editKeyForm: ref({ name: '', api_key: '' }),
      commonProviders: [{ text: 'Shodan', value: 'shodan', icon: 'mdi-radar' }],
      sortedApiKeys: computed(() => []),
      isFormValid: computed(() => false),
      validateProvider: vi.fn(),
      validateApiKey: vi.fn(),
      validateName: vi.fn(),
      loadApiKeys: vi.fn().mockResolvedValue(undefined),
      addApiKey: vi.fn(),
      updateApiKey: vi.fn(),
      deleteApiKey: vi.fn(),
      openAddDialog: vi.fn(),
      openEditDialog: vi.fn(),
      closeAddDialog: vi.fn(),
      closeEditDialog: vi.fn(),
      handleProviderChange: vi.fn(),
      getProviderIcon: vi.fn(),
      getProviderDisplayName: vi.fn(),
    })

    const wrapper = shallowMount(ApiKeyManagementCard, {
      global: { stubs: vuetifyStubs },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="select-item"]').text()).toContain('mdi-radar')
  })

  it('handles the Vuetify 4 model update event for the case-number prefix', async () => {
    const onPrefixChange = vi.fn()
    useSystemConfiguration.mockReturnValue({
      selectedTemplate: ref('PREFIX-YYMM-NN'),
      caseNumberPrefix: ref('CASE'),
      configLoading: ref(false),
      exampleCaseNumber: ref('CASE-2609-01'),
      templateOptions: [],
      isConfigChanged: computed(() => true),
      isConfigValid: computed(() => true),
      validatePrefix: vi.fn(() => true),
      onTemplateChange: vi.fn(),
      onPrefixChange,
      loadConfiguration: vi.fn().mockResolvedValue(undefined),
      saveConfiguration: vi.fn(),
      resetConfiguration: vi.fn(),
    })

    const wrapper = shallowMount(SystemConfigurationCard, {
      global: { stubs: vuetifyStubs },
    })
    await wrapper.get('input[aria-label="Prefix (2-8 letters/numbers)"]').setValue('INV')

    expect(onPrefixChange).toHaveBeenCalledWith('INV')
  })
})
