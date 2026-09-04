import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NewCaseModal from '../NewCaseModal.vue'
import { caseService } from '@/services/case'

const mocks = vi.hoisted(() => ({
  getClients: vi.fn(),
  getUsers: vi.fn(),
}))

vi.mock('@/services/client', () => ({ clientService: { getClients: mocks.getClients } }))
vi.mock('@/services/user', () => ({ userService: { getUsers: mocks.getUsers } }))
vi.mock('@/services/case', () => ({
  caseService: { createCase: vi.fn(), addUserToCase: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ requiresAdmin: () => true }) }))

const DialogStub = defineComponent({
  inheritAttrs: false,
  props: { modelValue: Boolean },
  template: '<section v-if="modelValue" role="dialog" v-bind="$attrs"><slot /></section>',
})
const FormStub = defineComponent({
  setup(_, { expose }) {
    expose({ validate: async () => ({ valid: true }), reset: vi.fn() })
  },
  template: '<form><slot /></form>',
})
const TextFieldStub = defineComponent({
  props: { label: String, modelValue: [String, Number] },
  emits: ['update:modelValue'],
  template:
    '<input :aria-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})
const SelectStub = defineComponent({
  props: { label: String, modelValue: [String, Number] },
  emits: ['update:modelValue'],
  template: '<div :data-label="label"><slot /></div>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})
const ModalActionsStub = defineComponent({
  emits: ['cancel', 'submit'],
  template:
    '<div><button data-testid="cancel" @click="$emit(\'cancel\')">Cancel</button><button data-testid="submit" @click="$emit(\'submit\')">Create Case</button></div>',
})
const TooltipStub = defineComponent({
  template: '<span><slot name="activator" :props="{}" /><slot /></span>',
})
const PassthroughStub = defineComponent({
  template: '<div><slot name="prepend" /><slot /><slot name="append" /></div>',
})

const global = {
  stubs: {
    VDialog: DialogStub,
    VForm: FormStub,
    VTextField: TextFieldStub,
    VSelect: SelectStub,
    VBtn: ButtonStub,
    VTooltip: TooltipStub,
    VAlert: PassthroughStub,
    VAlertTitle: PassthroughStub,
    VAvatar: PassthroughStub,
    VCard: PassthroughStub,
    VCardText: PassthroughStub,
    VCardTitle: PassthroughStub,
    VCheckbox: PassthroughStub,
    VChip: PassthroughStub,
    VCol: PassthroughStub,
    VIcon: PassthroughStub,
    VList: PassthroughStub,
    VListItem: PassthroughStub,
    VListItemSubtitle: PassthroughStub,
    VListItemTitle: PassthroughStub,
    VRow: PassthroughStub,
    ModalActions: ModalActionsStub,
  },
}

describe('NewCaseModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getClients.mockResolvedValue([{ id: 3, name: 'Client' }])
    mocks.getUsers.mockResolvedValue([
      { id: 9, email: 'analyst@example.org', username: 'analyst', role: 'Analyst' },
    ])
  })

  it('closes with a warning after a created case has an assignment failure', async () => {
    const newCase = { id: 42, case_number: 'CASE-042', title: 'Investigation' }
    caseService.createCase.mockResolvedValue(newCase)
    caseService.addUserToCase.mockRejectedValue({
      response: { data: { message: 'Assignment service unavailable' } },
    })
    const wrapper = mount(NewCaseModal, {
      props: { isOpen: true },
      global,
    })
    await flushPromises()

    await wrapper.get('[aria-label="Title"]').setValue('Investigation')
    wrapper
      .findAllComponents(SelectStub)
      .find((select) => select.props('label') === 'Client')
      .vm.$emit('update:modelValue', 3)
    wrapper
      .findAllComponents(SelectStub)
      .find((select) => select.props('label') === 'Select User')
      .vm.$emit('update:modelValue', 9)
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text().trim() === 'Add User')
      .trigger('click')
    expect(
      wrapper.get('[aria-label="Analysts cannot be set as leads for analyst@example.org"]'),
    ).toBeTruthy()
    expect(wrapper.get('[aria-label="Remove analyst@example.org from selection"]')).toBeTruthy()

    await wrapper.get('[data-testid="submit"]').trigger('click')
    await flushPromises()

    expect(caseService.createCase).toHaveBeenCalledOnce()
    expect(caseService.addUserToCase).toHaveBeenCalledWith(42, 9, false)
    expect(wrapper.emitted('created')).toEqual([
      [
        newCase,
        {
          assignmentWarning: '1 user assignment failed: Assignment service unavailable',
        },
      ],
    ])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
