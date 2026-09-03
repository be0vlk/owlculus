import { defineComponent, nextTick } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseDashboard from '../CaseDashboard.vue'

const mocks = vi.hoisted(() => ({
  exportCase: vi.fn(),
  downloadBlob: vi.fn(),
  getCase: vi.fn(),
  getClient: vi.fn(),
  getFolderTree: vi.fn(),
  getCaseExecutions: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '42' }, query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'Investigator' } }),
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

const mountDashboard = async () => {
  const wrapper = shallowMount(CaseDashboard, {
    global: {
      stubs: {
        BaseDashboard: BaseDashboardStub,
        VBtn: ButtonStub,
        VBtnGroup: defineComponent({ template: '<div><slot /></div>' }),
        VSnackbar: SnackbarStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('CaseDashboard export', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})
