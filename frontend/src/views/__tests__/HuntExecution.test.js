import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HuntExecution from '../HuntExecution.vue'

const mocks = vi.hoisted(() => ({
  execution: null,
  exportExecution: vi.fn(),
  downloadBlob: vi.fn(),
  showNotification: vi.fn(),
  getExecution: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/huntStore.js', () => ({
  useHuntStore: () => ({
    activeExecutions: {},
    getExecution: mocks.getExecution,
    subscribeToExecution: vi.fn(),
    unsubscribeFromExecution: vi.fn(),
    cancelExecution: vi.fn(),
  }),
}))

vi.mock('@/services/hunt', () => ({
  huntService: { exportExecution: mocks.exportExecution },
}))

vi.mock('@/utils/download', () => ({ downloadBlob: mocks.downloadBlob }))

vi.mock('@/composables/useNotifications', () => ({
  useNotifications: () => ({ showNotification: mocks.showNotification }),
}))

const BaseDashboardStub = defineComponent({
  template: '<div><slot name="header-actions" /><slot /></div>',
})
const MenuStub = defineComponent({
  template: '<div data-testid="export-menu"><slot name="activator" :props="{}" /><slot /></div>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  template: '<button :disabled="disabled"><slot /></button>',
})
const ListItemStub = defineComponent({
  props: { title: String, disabled: Boolean },
  emits: ['click'],
  template:
    '<button :data-testid="`export-${title.split(\' \').at(-1).toLowerCase()}`" :disabled="disabled" @click="$emit(\'click\')">{{ title }}</button>',
})

const mountExecution = async (status) => {
  mocks.execution = {
    id: 7,
    case_id: 42,
    status,
    progress: 1,
    initial_parameters: {},
    context_data: null,
    created_at: '2026-09-01T00:00:00Z',
    created_by_id: 1,
    hunt: { display_name: 'Person Hunt', category: 'person' },
    steps: [],
  }
  mocks.getExecution.mockResolvedValue(mocks.execution)
  const wrapper = shallowMount(HuntExecution, {
    global: {
      stubs: {
        BaseDashboard: BaseDashboardStub,
        VMenu: MenuStub,
        VBtn: ButtonStub,
        VList: defineComponent({ template: '<div><slot /></div>' }),
        VListItem: ListItemStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('HuntExecution exports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it.each(['completed', 'partial', 'failed', 'cancelled'])(
    'shows the export menu for a %s execution',
    async (status) => {
      const wrapper = await mountExecution(status)

      expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(true)
    },
  )

  it.each(['pending', 'running'])('hides the export menu for a %s execution', async (status) => {
    const wrapper = await mountExecution(status)

    expect(wrapper.find('[data-testid="export-menu"]').exists()).toBe(false)
  })

  it.each(['pdf', 'json'])('downloads a backend-generated %s export', async (format) => {
    const artifact = {
      blob: new Blob(['export']),
      headers: { 'content-disposition': `attachment; filename="execution.${format}"` },
    }
    mocks.exportExecution.mockResolvedValue(artifact)
    const wrapper = await mountExecution('failed')

    await wrapper.get(`[data-testid="export-${format}"]`).trigger('click')
    await flushPromises()

    expect(mocks.exportExecution).toHaveBeenCalledWith(7, format)
    expect(mocks.downloadBlob).toHaveBeenCalledWith(artifact, `hunt-execution-7.${format}`)
    expect(mocks.showNotification).toHaveBeenCalledWith('Results exported successfully', 'success')
  })
})
