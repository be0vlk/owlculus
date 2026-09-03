import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import EntityDataTable from '../EntityDataTable.vue'
import { downloadBlob } from '@/utils/download'

vi.mock('@/utils/download', () => ({ downloadBlob: vi.fn() }))

const DataTableStub = defineComponent({ template: '<div><slot name="top" /></div>' })
const MenuStub = defineComponent({
  template: '<div><slot name="activator" :props="{}" /><slot /></div>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
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
    VRow: PassthroughStub,
    VCol: PassthroughStub,
    VToolbar: PassthroughStub,
    VSpacer: PassthroughStub,
    VIcon: PassthroughStub,
    VDialog: PassthroughStub,
    VCard: PassthroughStub,
    VCardTitle: PassthroughStub,
    VCardText: PassthroughStub,
    VCardActions: PassthroughStub,
    VSnackbar: PassthroughStub,
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
      'Failed to export entities',
    )
  })
})
