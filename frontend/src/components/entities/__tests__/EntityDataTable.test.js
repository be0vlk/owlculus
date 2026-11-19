import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import EntityDataTable from '../EntityDataTable.vue'
import { downloadBlob } from '@/utils/download'
import { entityService } from '@/services/entity'

vi.mock('@/utils/download', () => ({ downloadBlob: vi.fn() }))
vi.mock('@/services/entity', () => ({
  entityService: { getCaseEntities: vi.fn(), exportEntities: vi.fn(), deleteEntity: vi.fn() },
}))

const DataTableStub = defineComponent({
  props: {
    modelValue: { type: Array, default: () => [] },
    items: { type: Array, default: () => [] },
    itemsLength: { type: Number, default: 0 },
    loading: Boolean,
  },
  emits: ['update:modelValue', 'click:row'],
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
    VDataTable: DataTableStub,
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
    VDivider: PassthroughStub,
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
  entityService.getCaseEntities.mockResolvedValue(entities)
  if (exportError) entityService.exportEntities.mockRejectedValue(exportError)
  else entityService.exportEntities.mockResolvedValue(download)
  const wrapper = mount(EntityDataTable, { props: { caseId: 42 }, global })
  await flushPromises()
  return { wrapper, download }
}

const button = (wrapper, text) =>
  wrapper.findAll('button').find((item) => item.text().trim() === text)

const confirmDeletion = async (wrapper) => {
  const dialog = wrapper.get('[role="dialog"][aria-label="Confirm Deletion"]')
  await button(dialog, 'Delete').trigger('click')
  await flushPromises()
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
      const { wrapper, download } = await mountTable()
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

    expect(wrapper.get('[data-testid="entity-action-error"]').text()).toContain(
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
    expect(dialog.attributes('aria-label')).toBe('Confirm Deletion')
    expect(dialog.text()).toContain('Are you sure you want to delete this entity?')
    expect(dialog.text()).toContain('This action cannot be undone.')

    await button(dialog, 'Cancel').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(entityService.deleteEntity).not.toHaveBeenCalled()
  })

  it('reports a delete failure', async () => {
    const { wrapper } = await mountTable()
    entityService.deleteEntity.mockRejectedValue({
      response: { data: { detail: 'The entity is still referenced by evidence' } },
    })

    await wrapper.get('[aria-label="Delete Needle Person"]').trigger('click')
    await confirmDeletion(wrapper)

    expect(wrapper.get('[data-testid="entity-action-error"]').text()).toContain(
      'The entity is still referenced by evidence',
    )
    expect(wrapper.emitted('deleted')).toBeUndefined()
  })

  it('keeps failed items selected after a partial bulk deletion so they can be retried', async () => {
    const remainingEntity = {
      id: 2,
      entity_type: 'person',
      data: { first_name: 'Retry', last_name: 'Person' },
      created_at: '2026-09-02T00:00:00Z',
    }
    entityService.getCaseEntities
      .mockResolvedValueOnce([matchingEntity, remainingEntity])
      .mockResolvedValue([remainingEntity])
    entityService.deleteEntity
      .mockResolvedValueOnce()
      .mockRejectedValueOnce(new Error('Deletion service unavailable'))
      .mockResolvedValueOnce()
    const wrapper = mount(EntityDataTable, { props: { caseId: 42 }, global })
    await flushPromises()

    wrapper
      .findComponent(DataTableStub)
      .vm.$emit('update:modelValue', [matchingEntity, remainingEntity])
    await flushPromises()
    await button(wrapper, 'Delete (2)').trigger('click')
    await confirmDeletion(wrapper)

    expect(entityService.deleteEntity.mock.calls).toEqual([
      [42, matchingEntity.id],
      [42, remainingEntity.id],
    ])
    expect(wrapper.emitted('deleted')).toEqual([[[matchingEntity]]])
    expect(wrapper.get('[data-testid="entity-action-error"]').text()).toContain(
      '1 entity could not be deleted: Deletion service unavailable',
    )
    expect(wrapper.findComponent(DataTableStub).props('items')).toEqual([remainingEntity])

    await button(wrapper, 'Delete (1)').trigger('click')
    await confirmDeletion(wrapper)

    expect(entityService.deleteEntity).toHaveBeenLastCalledWith(42, remainingEntity.id)
    expect(button(wrapper, 'Delete (1)')).toBeUndefined()
  })

  it('reports a loading failure and lets the user retry', async () => {
    entityService.getCaseEntities.mockRejectedValueOnce(new Error('Entity service unavailable'))
    const wrapper = mount(EntityDataTable, { props: { caseId: 42 }, global })
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
})

describe('EntityDataTable with Vuetify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    vi.unstubAllGlobals()
  })

  it('filters by type and search, and sorts IPv4 names numerically', async () => {
    const ip = (id, address) => ({
      id,
      entity_type: 'ip_address',
      data: { ip_address: address },
      created_at: `2026-09-0${id}T00:00:00Z`,
    })
    entityService.getCaseEntities.mockResolvedValue([
      ip(1, '10.0.0.2'),
      ip(2, '9.0.0.1'),
      {
        ...matchingEntity,
        id: 3,
        data: { ...matchingEntity.data, description: 'witness' },
        created_at: '2026-09-03T00:00:00Z',
      },
    ])
    const wrapper = mount(EntityDataTable, {
      props: { caseId: 42 },
      global: { plugins: [createVuetify({ components, directives, theme: false })] },
    })
    await flushPromises()
    const names = () =>
      wrapper.findAll('tbody tr').map((row) => row.findAll('td')[2]?.text().split('\n')[0])

    // Newest first until the user sorts.
    expect(names()).toEqual(['Needle Person', '9.0.0.1', '10.0.0.2'])

    await wrapper
      .findAll('th')
      .find((th) => th.text().includes('Name'))
      .trigger('click')
    expect(names()).toEqual(['9.0.0.1', '10.0.0.2', 'Needle Person'])

    await wrapper
      .findAll('.v-chip')
      .find((chip) => chip.text().includes('IP Address'))
      .trigger('click')
    expect(names()).toEqual(['9.0.0.1', '10.0.0.2'])

    await wrapper
      .findAll('.v-chip')
      .find((chip) => chip.text().includes('IP Address'))
      .trigger('click')
    await wrapper.get('[data-testid="entity-search"] input').setValue('WITNESS')
    expect(names()).toEqual(['Needle Person'])
  })
})
