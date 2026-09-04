import { defineComponent, nextTick } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseDashboard from '../CaseDashboard.vue'

const mocks = vi.hoisted(() => ({
  exportCase: vi.fn(),
  refreshCases: vi.fn(),
  recoverUnavailable: vi.fn(),
  downloadBlob: vi.fn(),
  getCase: vi.fn(),
  getClient: vi.fn(),
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

vi.mock('@/stores/activeCase', () => ({
  useActiveCaseStore: () => ({
    activeCaseId: 42,
    refresh: mocks.refreshCases,
    recoverUnavailable: mocks.recoverUnavailable,
  }),
}))

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
  entityService: { getEntity: vi.fn() },
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

const mountDashboard = async () => {
  const wrapper = shallowMount(CaseDashboard, {
    global: {
      stubs: {
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
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('CaseDashboard export', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
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
})
