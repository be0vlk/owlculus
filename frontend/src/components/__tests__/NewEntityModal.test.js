import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NewEntityModal from '../NewEntityModal.vue'
import { entityService } from '@/services/entity'

vi.mock('@/services/entity', () => ({
  entityService: { createEntity: vi.fn() },
}))

const DialogStub = defineComponent({
  inheritAttrs: false,
  props: { modelValue: Boolean },
  template: '<section v-if="modelValue" role="dialog" v-bind="$attrs"><slot /></section>',
})
const CardStub = defineComponent({
  props: { title: String },
  template: '<div><h2 v-if="title">{{ title }}</h2><slot /></div>',
})
const FormStub = defineComponent({
  emits: ['submit'],
  template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  template:
    '<button :disabled="disabled" :data-loading="String(loading)" @click="$emit(\'click\')"><slot /></button>',
})
const PersonFormStub = defineComponent({
  props: { modelValue: { type: Object, required: true } },
  emits: ['update:modelValue'],
  template:
    '<input aria-label="First Name" :value="modelValue.first_name" @input="$emit(\'update:modelValue\', { ...modelValue, first_name: $event.target.value })" />',
})
const AlertStub = defineComponent({ template: '<div role="alert"><slot /></div>' })
const PassthroughStub = defineComponent({ template: '<div><slot /></div>' })

const global = {
  stubs: {
    VDialog: DialogStub,
    VCard: CardStub,
    VCardText: PassthroughStub,
    VCardTitle: PassthroughStub,
    VCardActions: PassthroughStub,
    VAlert: AlertStub,
    VBtn: ButtonStub,
    VDivider: PassthroughStub,
    VForm: FormStub,
    VIcon: PassthroughStub,
    VSpacer: PassthroughStub,
    VTab: PassthroughStub,
    VTabs: PassthroughStub,
    VTabsWindow: PassthroughStub,
    VTabsWindowItem: PassthroughStub,
    PersonForm: PersonFormStub,
    CompanyForm: PassthroughStub,
    DomainForm: PassthroughStub,
    IpAddressForm: PassthroughStub,
    VehicleForm: PassthroughStub,
  },
}

function addEntityButton(wrapper) {
  return wrapper.findAll('button').find((button) => button.text().trim() === 'Add Entity')
}

describe('NewEntityModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has an accessible dialog name and does not submit an invalid form via Enter', async () => {
    const wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '42' },
      global,
    })

    expect(wrapper.get('[role="dialog"]').attributes('aria-label')).toBe('Add New Entity')
    expect(addEntityButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(entityService.createEntity).not.toHaveBeenCalled()
  })

  it('submits valid entity data once and reports the created entity', async () => {
    const createdEntity = {
      id: 7,
      entity_type: 'person',
      data: { first_name: 'Ada', last_name: '' },
    }
    entityService.createEntity.mockResolvedValue(createdEntity)
    const wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '42' },
      global,
    })

    await wrapper.get('[aria-label="First Name"]').setValue('Ada')
    await addEntityButton(wrapper).trigger('click')
    await flushPromises()

    expect(entityService.createEntity).toHaveBeenCalledOnce()
    expect(entityService.createEntity).toHaveBeenCalledWith('42', {
      entity_type: 'person',
      data: expect.objectContaining({ first_name: 'Ada' }),
    })
    expect(wrapper.emitted('created')).toEqual([[createdEntity]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('keeps the dialog open and presents the API error when creation fails', async () => {
    entityService.createEntity.mockRejectedValue({
      response: { data: { detail: 'An entity with that identity already exists' } },
    })
    const wrapper = mount(NewEntityModal, {
      props: { show: true, caseId: '42' },
      global,
    })

    await wrapper.get('[aria-label="First Name"]').setValue('Ada')
    await addEntityButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'An entity with that identity already exists',
    )
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
  })
})
