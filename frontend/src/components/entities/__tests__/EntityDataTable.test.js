import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import EntityDataTable from '../EntityDataTable.vue'
import { downloadBlob } from '@/utils/download'

vi.mock('@/utils/download', () => ({ downloadBlob: vi.fn() }))

const DataTableStub = defineComponent({
  props: {
    modelValue: { type: Array, default: () => [] },
    items: { type: Array, default: () => [] },
    itemsLength: { type: Number, default: 0 },
    loading: Boolean,
    sortBy: { type: Array, default: () => [] },
  },
  emits: ['update:modelValue', 'update:options', 'update:sortBy', 'click:row'],
  template: `<section aria-label="Entities">
    <slot name="top" />
    <div v-if="loading" role="status">Loading entities</div>
    <div v-else-if="items[0]" data-testid="entity-row" @click="$emit('click:row', $event, { item: items[0] })">
      <span>{{ items[0].data.first_name || items[0].data.name }}</span>
      <slot name="item.actions" :item="items[0]" />
    </div>
    <slot v-else name="no-data" />
  </section>`,
})
const MenuStub = defineComponent({
  template: '<div><slot name="activator" :props="{}" /><slot /></div>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
})
const ListItemStub = defineComponent({
  props: { title: String },
  emits: ['click'],
  template: '<button @click="$emit(\'click\')">{{ title }}</button>',
})
const TextFieldStub = defineComponent({
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template:
    '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})
const ChipGroupStub = defineComponent({
  emits: ['update:modelValue'],
  template:
    '<button data-testid="select-person" @click="$emit(\'update:modelValue\', [\'person\'])"><slot /></button>',
})
const PassthroughStub = defineComponent({ template: '<div><slot /></div>' })
const DialogStub = defineComponent({
  inheritAttrs: false,
  props: { modelValue: Boolean },
  template: '<section v-if="modelValue" role="dialog" v-bind="$attrs"><slot /></section>',
})
const SnackbarStub = defineComponent({
  inheritAttrs: false,
  props: { modelValue: Boolean },
  template: '<div v-if="modelValue" v-bind="$attrs"><slot /><slot name="actions" /></div>',
})
const AlertStub = defineComponent({ template: '<div role="alert"><slot /></div>' })

const global = {
  stubs: {
    VDataTableServer: DataTableStub,
    VMenu: MenuStub,
    VBtn: ButtonStub,
    VList: PassthroughStub,
    VListItem: ListItemStub,
    VTextField: TextFieldStub,
    VChipGroup: ChipGroupStub,
    VChip: PassthroughStub,
    VContainer: PassthroughStub,
    VRow: PassthroughStub,
    VCol: PassthroughStub,
    VToolbar: PassthroughStub,
    VSpacer: PassthroughStub,
    VIcon: PassthroughStub,
    VDialog: DialogStub,
    VCard: PassthroughStub,
    VCardTitle: PassthroughStub,
    VCardText: PassthroughStub,
    VCardActions: PassthroughStub,
    VAlert: AlertStub,
    VSnackbar: SnackbarStub,
    VSkeletonLoader: PassthroughStub,
  },
}

const matchingEntity = {
  id: 1,
  entity_type: 'person',
  data: { first_name: 'Needle', last_name: 'Person' },
  created_at: '2026-09-01T00:00:00Z',
}

const mountTable = async (entities = [matchingEntity], exportError = null) => {
  const download = {
    blob: new Blob(['export']),
    headers: { 'content-disposition': 'attachment; filename="export.csv"' },
  }
  const entityService = {
    getCaseEntities: vi.fn().mockResolvedValue(entities),
    exportEntities: exportError
      ? vi.fn().mockRejectedValue(exportError)
      : vi.fn().mockResolvedValue(download),
    deleteEntity: vi.fn(),
  }
  const wrapper = mount(EntityDataTable, {
    props: { caseId: 42, entityService },
    global,
  })
  await flushPromises()
  return { wrapper, entityService, download }
}

describe('EntityDataTable exports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it.each(['csv', 'json'])(
    'exports current filters as %s through the download helper',
    async (format) => {
      const { wrapper, entityService, download } = await mountTable()
      await wrapper.get('[data-testid="select-person"]').trigger('click')
      await wrapper.get('[data-testid="entity-search"]').setValue('needle')
      await flushPromises()

      await wrapper.get(`[data-testid="export-${format}"]`).trigger('click')
      await flushPromises()

      expect(entityService.exportEntities).toHaveBeenCalledWith(42, {
        format,
        entityTypes: ['person'],
        search: 'needle',
      })
      expect(downloadBlob).toHaveBeenCalledWith(
        download,
        expect.stringMatching(new RegExp(`^case-42-entities-\\d{4}-\\d{2}-\\d{2}\\.${format}$`)),
      )
    },
  )

  it('disables export when no entity matches the filters', async () => {
    const { wrapper } = await mountTable([])

    expect(wrapper.get('[data-testid="entity-export-button"]').attributes('disabled')).toBeDefined()
  })

  it('shows an error notification when an export fails', async () => {
    const { wrapper } = await mountTable(
      [matchingEntity],
      new Error('The export service is unavailable'),
    )

    await wrapper.get('[data-testid="export-csv"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="entity-export-error"]').text()).toContain(
      'The export service is unavailable',
    )
  })
})

describe('EntityDataTable workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('opens rows and keeps named row actions separate from safe-delete confirmation', async () => {
    const { wrapper } = await mountTable()

    await wrapper.get('[data-testid="entity-row"]').trigger('click')
    expect(wrapper.emitted('view')).toEqual([[matchingEntity, expect.any(MouseEvent)]])

    await wrapper.get('[aria-label="View Needle Person"]').trigger('click')
    expect(wrapper.emitted('view')).toHaveLength(2)
    expect(wrapper.emitted('view')[1]).toEqual([matchingEntity, expect.any(MouseEvent)])

    await wrapper.get('[aria-label="Delete Needle Person"]').trigger('click')
    expect(wrapper.emitted('view')).toHaveLength(2)

    const dialog = wrapper.get('[role="dialog"]')
    expect(dialog.attributes('aria-label')).toBe('Confirm Delete')
    expect(dialog.text()).toContain('Are you sure you want to delete this entity?')
    expect(dialog.text()).toContain('This action cannot be undone.')

    await dialog.get('button').trigger('click')

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('keeps the confirmation open and reports a delete failure', async () => {
    const { wrapper, entityService } = await mountTable()
    entityService.deleteEntity.mockRejectedValue({
      response: { data: { detail: 'The entity is still referenced by evidence' } },
    })

    await wrapper.get('[aria-label="Delete Needle Person"]').trigger('click')
    const dialog = wrapper.get('[role="dialog"]')
    const deleteButton = dialog
      .findAll('button')
      .find((button) => button.text().trim() === 'Delete')
    await deleteButton.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="entity-delete-error"]').text()).toContain(
      'The entity is still referenced by evidence',
    )
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.emitted('deleted')).toBeUndefined()
  })

  it('removes successful items from a partial bulk deletion before retrying failures', async () => {
    const remainingEntity = {
      id: 2,
      entity_type: 'person',
      data: { first_name: 'Retry', last_name: 'Person' },
      created_at: '2026-09-02T00:00:00Z',
    }
    const entityService = {
      getCaseEntities: vi
        .fn()
        .mockResolvedValueOnce([matchingEntity, remainingEntity])
        .mockResolvedValue([remainingEntity]),
      exportEntities: vi.fn(),
      deleteEntity: vi
        .fn()
        .mockResolvedValueOnce()
        .mockRejectedValueOnce(new Error('Deletion service unavailable'))
        .mockResolvedValueOnce(),
    }
    const wrapper = mount(EntityDataTable, {
      props: { caseId: 42, entityService },
      global,
    })
    await flushPromises()

    wrapper
      .findComponent(DataTableStub)
      .vm.$emit('update:modelValue', [matchingEntity, remainingEntity])
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Delete (2)'))
      .trigger('click')
    let dialog = wrapper.get('[role="dialog"]')
    await dialog
      .findAll('button')
      .find((button) => button.text().trim() === 'Delete')
      .trigger('click')
    await flushPromises()

    expect(entityService.deleteEntity.mock.calls).toEqual([
      [42, matchingEntity.id],
      [42, remainingEntity.id],
    ])
    expect(wrapper.emitted('deleted')).toEqual([[[matchingEntity]]])
    expect(wrapper.get('[data-testid="entity-delete-error"]').text()).toContain(
      '1 entity could not be deleted: Deletion service unavailable',
    )
    dialog = wrapper.get('[role="dialog"]')
    expect(dialog.text()).toContain('delete this entity')
    expect(wrapper.findComponent(DataTableStub).props('items')).toEqual([remainingEntity])

    await dialog
      .findAll('button')
      .find((button) => button.text().trim() === 'Delete')
      .trigger('click')
    await flushPromises()

    expect(entityService.deleteEntity).toHaveBeenLastCalledWith(42, remainingEntity.id)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('reports a loading failure and lets the user retry', async () => {
    const entityService = {
      getCaseEntities: vi.fn().mockRejectedValueOnce(new Error('Entity service unavailable')),
      exportEntities: vi.fn(),
      deleteEntity: vi.fn(),
    }
    const wrapper = mount(EntityDataTable, {
      props: { caseId: 42, entityService },
      global,
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="entity-load-error"]').text()).toContain(
      'Entity service unavailable',
    )

    entityService.getCaseEntities.mockResolvedValue([matchingEntity])
    await wrapper.get('[data-testid="retry-entity-load"]').trigger('click')
    await flushPromises()

    expect(entityService.getCaseEntities).toHaveBeenCalledTimes(2)
    expect(wrapper.findComponent(DataTableStub).props('items')).toEqual([matchingEntity])
    expect(wrapper.find('[data-testid="entity-load-error"]').exists()).toBe(false)
  })

  it('applies table sorting to the visible entities', async () => {
    const alphaEntity = {
      id: 2,
      entity_type: 'person',
      data: { first_name: 'Alpha', last_name: 'Person' },
      created_at: '2026-08-01T00:00:00Z',
    }
    const { wrapper } = await mountTable([matchingEntity, alphaEntity])
    const table = wrapper.findComponent(DataTableStub)

    table.vm.$emit('update:sortBy', [{ key: 'name', order: 'asc' }])
    await flushPromises()
    table.vm.$emit('update:options')
    await flushPromises()

    expect(table.props('items').map((entity) => entity.data.first_name)).toEqual([
      'Alpha',
      'Needle',
    ])
  })
})
