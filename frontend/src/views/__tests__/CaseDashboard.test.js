import { defineComponent, h, nextTick, reactive } from 'vue'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import CaseDashboard from '../CaseDashboard.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  activeCase: null,
  exportCase: vi.fn(),
  refreshCases: vi.fn(),
  recoverUnavailable: vi.fn(),
  downloadBlob: vi.fn(),
  getCase: vi.fn(),
  getClient: vi.fn(),
  updateEntity: vi.fn(),
  refreshEntities: vi.fn(),
  getFolderTree: vi.fn(),
  getCaseExecutions: vi.fn(),
  replaceRoute: vi.fn(),
  route: { params: { id: '42' }, query: {} },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: vi.fn(), replace: mocks.replaceRoute }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'Investigator' } }),
}))

vi.mock('@/stores/activeCase', () => {
  mocks.activeCase = reactive({
    activeCaseId: 42,
    refresh: mocks.refreshCases,
    recoverUnavailable: mocks.recoverUnavailable,
  })
  return { useActiveCaseStore: () => mocks.activeCase }
})

vi.mock('@/stores/huntStore.js', () => ({
  useHuntStore: () => ({ getCaseExecutions: mocks.getCaseExecutions }),
}))

vi.mock('@/services/case', () => ({
  caseService: {
    exportCase: mocks.exportCase,
    getCase: mocks.getCase,
    updateCase: vi.fn(),
  },
}))

vi.mock('@/services/client', () => ({
  clientService: { getClient: mocks.getClient },
}))

vi.mock('@/services/entity', () => ({
  entityService: { getEntity: vi.fn(), updateEntity: mocks.updateEntity },
}))

vi.mock('@/services/evidence', () => ({
  evidenceService: { getFolderTree: mocks.getFolderTree },
}))

vi.mock('@/utils/download', () => ({ downloadBlob: mocks.downloadBlob }))

const BaseDashboardStub = defineComponent({
  template: '<div><slot name="header-actions" /><slot /></div>',
})
const PassthroughStub = defineComponent({ template: '<div><slot /></div>' })
const ButtonStub = defineComponent({
  inheritAttrs: false,
  props: { loading: Boolean },
  emits: ['click'],
  template:
    '<button v-bind="$attrs" :data-loading="String(loading)" @click="$emit(\'click\')"><slot /></button>',
})
const SnackbarStub = defineComponent({
  props: { modelValue: Boolean, color: String },
  template:
    '<div v-if="modelValue" data-testid="case-export-notification" :data-color="color"><slot /></div>',
})
const CaseTabsStub = defineComponent({
  name: 'CaseTabsStub',
  props: { modelValue: String },
  emits: ['update:modelValue'],
  template:
    '<div data-testid="case-tabs" :data-model-value="modelValue"><button data-testid="select-notes" @click="$emit(\'update:modelValue\', \'notes\')">Notes</button></div>',
})
const CaseDetailStub = defineComponent({
  name: 'CaseDetailStub',
  props: { caseData: Object },
  template: '<div data-testid="case-detail">{{ caseData.title }} {{ caseData.status }}</div>',
})
const EditCaseModalStub = defineComponent({
  name: 'EditCaseModalStub',
  emits: ['update'],
  template:
    "<button data-testid=\"emit-case-update\" @click=\"$emit('update', { title: 'Updated investigation', status: 'Closed' })\">Update</button>",
})

const mountDashboard = async (global = {}, keyedWorkspace = false) => {
  const root = keyedWorkspace
    ? defineComponent({
        setup: () => () => h(CaseDashboard, { key: mocks.activeCase.activeCaseId }),
      })
    : CaseDashboard
  const wrapper = shallowMount(root, {
    global: {
      ...global,
      stubs: {
        CaseDashboard: false,
        BaseDashboard: BaseDashboardStub,
        VBtn: ButtonStub,
        VBtnGroup: defineComponent({ template: '<div><slot /></div>' }),
        VCard: PassthroughStub,
        VCardText: PassthroughStub,
        VCardTitle: PassthroughStub,
        VRow: PassthroughStub,
        VCol: PassthroughStub,
        VSnackbar: SnackbarStub,
        CaseTabs: CaseTabsStub,
        CaseDetail: CaseDetailStub,
        EditCaseModal: EditCaseModalStub,
        ...global.stubs,
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function mountEditingDashboard() {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  vi.stubGlobal('visualViewport', new EventTarget())
  const EntityTableStub = defineComponent({
    emits: ['view'],
    methods: { refresh: mocks.refreshEntities },
    template: `<div>
        <button data-testid="view-a" @click="$emit('view', { id: 1, entity_type: 'person', data: { first_name: 'Ada', notes: '<p>A initial</p>' } })">A</button>
        <button data-testid="view-b" @click="$emit('view', { id: 2, entity_type: 'person', data: { first_name: 'Grace', notes: '<p>B initial</p>' } })">B</button>
      </div>`,
  })
  return mountDashboard(
    {
      plugins: [createVuetify({ components, directives, theme: false })],
      stubs: {
        ...Object.fromEntries(Object.keys(components).map((name) => [name, false])),
        EntityDataTable: EntityTableStub,
        CaseTabs: defineComponent({ template: '<div><slot active-tab="entities" /></div>' }),
        EntityDetailsModal: false,
        EntityTabContent: false,
        EntityFormField: false,
        EntityViewField: false,
        EntityNotesFullscreen: false,
        EntityModalActions: false,
        EditorToolbar: false,
        EditorContent: false,
        MaybeTransition: false,
        VIcon: true,
        VDialog: defineComponent({
          props: ['modelValue'],
          template: '<div v-if="modelValue"><slot /></div>',
        }),
      },
    },
    true,
  )
}

function editingControls(wrapper) {
  const button = (text) => wrapper.findAll('button').find((item) => item.text() === text)
  const tab = async (title) => {
    await wrapper
      .findAll('[role="tab"]')
      .find((item) => item.text() === title)
      .trigger('click')
    await flushPromises()
  }
  const input = (label) =>
    wrapper
      .findAll('.v-input')
      .find((item) => item.findAll('label').some((item) => item.text() === label))
      .get('input')
  const notes = () => wrapper.get('[aria-label="Entity notes"]')
  const typeNotes = async (html) => {
    notes().element.innerHTML = html
    await notes().trigger('input')
  }
  return { button, tab, input, notes, typeNotes }
}

describe('CaseDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
    mocks.activeCase.activeCaseId = 42
    mocks.getCase.mockResolvedValue({
      id: 42,
      case_number: 'CASE-042',
      title: 'Export case',
      client_id: 5,
    })
    mocks.getClient.mockResolvedValue({ id: 5, name: 'Client' })
    mocks.getFolderTree.mockResolvedValue([])
    mocks.getCaseExecutions.mockResolvedValue([])
  })

  it('shows loading while the bundle is prepared and then downloads it', async () => {
    let finishExport
    const artifact = {
      blob: new Blob(['archive']),
      headers: { 'content-disposition': 'attachment; filename="CASE-042-export.zip"' },
    }
    mocks.exportCase.mockReturnValue(
      new Promise((resolve) => {
        finishExport = () => resolve(artifact)
      }),
    )
    const wrapper = await mountDashboard()
    const exportButton = wrapper.get('[data-testid="case-export-button"]')

    await exportButton.trigger('click')
    await nextTick()

    expect(mocks.exportCase).toHaveBeenCalledWith(42)
    expect(exportButton.attributes('data-loading')).toBe('true')

    finishExport()
    await flushPromises()

    expect(mocks.downloadBlob).toHaveBeenCalledWith(artifact, 'CASE-042-export.zip')
    const notification = wrapper.get('[data-testid="case-export-notification"]')
    expect(notification.text()).toContain('Case exported successfully')
    expect(notification.attributes('data-color')).toBe('success')
    expect(exportButton.attributes('data-loading')).toBe('false')
  })

  it('notifies the user when preparing the bundle fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    mocks.exportCase.mockRejectedValue(new Error('network failed'))
    const wrapper = await mountDashboard()

    await wrapper.get('[data-testid="case-export-button"]').trigger('click')
    await flushPromises()

    expect(mocks.downloadBlob).not.toHaveBeenCalled()
    const notification = wrapper.get('[data-testid="case-export-notification"]')
    expect(notification.text()).toContain('Failed to export case')
    expect(notification.attributes('data-color')).toBe('error')
  })

  it('opens a valid tab from the URL and preserves tab changes in navigation state', async () => {
    mocks.route.query = { tab: 'evidence', highlight: '9' }
    const wrapper = await mountDashboard()
    expect(wrapper.get('[data-testid="case-tabs"]').attributes('data-model-value')).toBe('evidence')

    await wrapper.get('[data-testid="select-notes"]').trigger('click')

    expect(mocks.replaceRoute).toHaveBeenCalledWith({
      query: { tab: 'notes', highlight: '9' },
    })
  })

  it('falls back to the first available tab when the URL requests an unavailable tab', async () => {
    mocks.route.query = { tab: 'admin-only' }

    const wrapper = await mountDashboard()

    expect(wrapper.get('[data-testid="case-tabs"]').attributes('data-model-value')).toBe('entities')
  })

  it('applies successful edits emitted by the edit-case dialog', async () => {
    const wrapper = await mountDashboard()

    await wrapper.get('[data-testid="emit-case-update"]').trigger('click')

    expect(wrapper.get('[data-testid="case-detail"]').text()).toBe('Updated investigation Closed')
  })

  it.each(
    ['entity', 'case', 'reopened entity'].flatMap((replacement) =>
      ['note', 'form'].flatMap((operation) =>
        ['success', 'failure'].map((outcome) => ({ replacement, operation, outcome })),
      ),
    ),
  )(
    'isolates a late $operation $outcome after $replacement replacement',
    async ({ replacement, operation, outcome }) => {
      const wrapper = await mountEditingDashboard()
      const { button, tab, input, notes, typeNotes } = editingControls(wrapper)
      const writes = []
      mocks.updateEntity.mockImplementation(
        (_caseId, id, payload) =>
          new Promise((resolve, reject) => {
            writes.push({
              succeed: () => resolve({ id, ...payload }),
              fail: () => reject(new Error('Unavailable')),
            })
          }),
      )
      try {
        await wrapper.get('[data-testid="view-a"]').trigger('click')
        await flushPromises()
        await button('Edit Entity').trigger('click')
        await tab('Address')
        await input('City').setValue('Old submitted city')
        await input('Source for City').setValue('Old submitted source')
        await tab('Notes')
        vi.useFakeTimers()
        await typeNotes('<p>Old submitted notes</p>')
        if (operation === 'form') await button('Save Changes').trigger('click')
        else await vi.advanceTimersByTimeAsync(5000)
        await typeNotes('<p>Old newer notes</p>')
        expect(mocks.updateEntity).toHaveBeenCalledTimes(1)
        if (replacement === 'case') {
          mocks.activeCase.activeCaseId = 77
          await flushPromises()
          await wrapper.get('[data-testid="view-a"]').trigger('click')
        } else {
          await wrapper.get('[data-testid="view-b"]').trigger('click')
          if (replacement === 'reopened entity') {
            await flushPromises()
            await wrapper.get('[data-testid="view-a"]').trigger('click')
          }
        }
        await flushPromises()
        await button('Edit Entity').trigger('click')
        await tab('Address')
        await input('City').setValue('New private city')
        await input('Source for City').setValue('New private source')
        await tab('Notes')
        await typeNotes('<p>New private notes</p>')
        await vi.advanceTimersByTimeAsync(5000)
        const newTarget = [replacement === 'case' ? 77 : 42, replacement === 'entity' ? 2 : 1]
        expect(mocks.updateEntity.mock.calls[1].slice(0, 2)).toEqual(newTarget)
        writes[1].fail()
        await flushPromises()
        expect(wrapper.text()).toContain('Failed to save notes')
        if (outcome === 'success') writes[0].succeed()
        else writes[0].fail()
        await flushPromises()
        const expectedData = { first_name: 'Ada', notes: '<p>Old newer notes</p>' }
        if (operation === 'form' && outcome === 'success') {
          expectedData.address = { city: 'Old submitted city' }
          expectedData.sources = { 'address.city': 'Old submitted source' }
        }
        expect(mocks.updateEntity.mock.calls[2]).toEqual([
          42,
          1,
          { entity_type: 'person', data: expect.objectContaining(expectedData) },
        ])
        if (operation !== 'form' || outcome !== 'success') {
          expect(mocks.updateEntity.mock.calls[2][2].data.address).toBeUndefined()
          expect(mocks.updateEntity.mock.calls[2][2].data.sources).toBeUndefined()
        }
        writes[2].succeed()
        await flushPromises()
        expect(mocks.refreshEntities).not.toHaveBeenCalled()
        expect(notes().text()).toBe('New private notes')
        expect(notes().attributes('contenteditable')).toBe('true')
        expect(wrapper.text()).toContain('Failed to save notes')
        expect(wrapper.text()).not.toContain('Unavailable')
        expect(button('Save Changes').attributes('disabled')).toBeUndefined()
        await tab('Address')
        expect(input('City').element.value).toBe('New private city')
        expect(input('Source for City').element.value).toBe('New private source')
        await button('Save Changes').trigger('click')
        expect(mocks.updateEntity.mock.calls[3]).toEqual([
          ...newTarget,
          {
            entity_type: 'person',
            data: expect.objectContaining({
              first_name: replacement === 'entity' ? 'Grace' : 'Ada',
              address: { city: 'New private city' },
              sources: { 'address.city': 'New private source' },
              notes: '<p>New private notes</p>',
            }),
          },
        ])
        writes[3].succeed()
        await flushPromises()
        expect(mocks.refreshEntities).toHaveBeenCalledTimes(1)
        expect(wrapper.text()).toContain('View Mode')
        expect(wrapper.text()).not.toContain('Failed to save notes')
        wrapper.unmount()
        await vi.advanceTimersByTimeAsync(10000)
        expect(mocks.updateEntity).toHaveBeenCalledTimes(4)
      } finally {
        wrapper.unmount()
        vi.useRealTimers()
        vi.unstubAllGlobals()
      }
    },
  )

  it.each(['entity', 'case'])(
    'captures notes before debounce on %s replacement without disturbing a new pending form',
    async (replacement) => {
      const wrapper = await mountEditingDashboard()
      const { button, tab, input, notes, typeNotes } = editingControls(wrapper)
      const writes = []
      mocks.updateEntity.mockImplementation(
        (_caseId, id, payload) =>
          new Promise((resolve) => {
            writes.push(() => resolve({ id, ...payload }))
          }),
      )
      try {
        await wrapper.get('[data-testid="view-a"]').trigger('click')
        await flushPromises()
        await button('Edit Entity').trigger('click')
        await tab('Notes')
        vi.useFakeTimers()
        await typeNotes('<p>Captured on navigation</p>')
        expect(mocks.updateEntity).not.toHaveBeenCalled()
        if (replacement === 'case') {
          mocks.activeCase.activeCaseId = 77
          await flushPromises()
        }
        await wrapper.get('[data-testid="view-b"]').trigger('click')
        await flushPromises()
        expect(mocks.updateEntity).toHaveBeenCalledExactlyOnceWith(42, 1, {
          entity_type: 'person',
          data: { first_name: 'Ada', notes: '<p>Captured on navigation</p>' },
        })
        await button('Edit Entity').trigger('click')
        await tab('Address')
        await input('City').setValue('New city')
        await input('Source for City').setValue('New source')
        await tab('Notes')
        await typeNotes('<p>New form notes</p>')
        await button('Save Changes').trigger('click')
        await typeNotes('<p>Newer private notes</p>')
        expect(button('Save Changes').attributes('disabled')).toBeDefined()
        writes[0]()
        await flushPromises()
        expect(notes().text()).toBe('Newer private notes')
        expect(notes().attributes('contenteditable')).toBe('true')
        expect(button('Save Changes').attributes('disabled')).toBeDefined()
        expect(button('Cancel').attributes('disabled')).toBeDefined()
        expect(mocks.refreshEntities).not.toHaveBeenCalled()
        await tab('Address')
        expect(input('City').element.value).toBe('New city')
        expect(input('Source for City').element.value).toBe('New source')
        writes[1]()
        await flushPromises()
        expect(mocks.updateEntity.mock.calls[2]).toEqual([
          replacement === 'case' ? 77 : 42,
          2,
          {
            entity_type: 'person',
            data: expect.objectContaining({
              first_name: 'Grace',
              address: { city: 'New city' },
              sources: { 'address.city': 'New source' },
              notes: '<p>Newer private notes</p>',
            }),
          },
        ])
        writes[2]()
        await flushPromises()
        expect(mocks.refreshEntities).toHaveBeenCalledTimes(2)
        wrapper.unmount()
        await vi.advanceTimersByTimeAsync(10000)
        expect(mocks.updateEntity).toHaveBeenCalledTimes(3)
      } finally {
        wrapper.unmount()
        vi.useRealTimers()
        vi.unstubAllGlobals()
      }
    },
  )

  it('keeps pending notes with their entity when selection changes during a save', async () => {
    const wrapper = await mountEditingDashboard()
    const notesTab = () => wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'Notes')
    const button = (text) => wrapper.findAll('button').find((button) => button.text() === text)
    try {
      await wrapper.get('[data-testid="view-a"]').trigger('click')
      await flushPromises()
      await notesTab().trigger('click')
      await button('Edit Entity').trigger('click')
      await flushPromises()
      vi.useFakeTimers()
      let finishSave
      mocks.updateEntity.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishSave = resolve
          }),
      )
      const box = wrapper.get('[aria-label="Entity notes"]')
      box.element.innerHTML = '<p>A pending</p>'
      await box.trigger('input')
      await vi.advanceTimersByTimeAsync(5000)
      await wrapper.get('[data-testid="view-b"]').trigger('click')
      await flushPromises()
      await notesTab().trigger('click')
      await flushPromises()
      expect(wrapper.get('[aria-label="Entity notes"]').text()).toBe('B initial')
      finishSave({ id: 1, ...mocks.updateEntity.mock.calls[0][2] })
      await flushPromises()
      await button('Close').trigger('click')
      await flushPromises()
      expect(mocks.updateEntity).toHaveBeenCalledExactlyOnceWith(42, 1, {
        entity_type: 'person',
        data: { first_name: 'Ada', notes: '<p>A pending</p>' },
      })
    } finally {
      wrapper.unmount()
      vi.useRealTimers()
      vi.unstubAllGlobals()
    }
  })
})
