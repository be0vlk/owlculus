import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import MainDashboard from '../MainDashboard.vue'

const mocks = vi.hoisted(() => ({ loadData: vi.fn(), selectCase: vi.fn() }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))
vi.mock('@/stores/activeCase', () => ({ useActiveCaseStore: () => ({ select: mocks.selectCase }) }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ requiresAdmin: () => true, user: { id: 1 } }),
}))
vi.mock('@/composables/useDashboard', async () => {
  const { ref } = await import('vue')
  return {
    useDashboard: () => ({
      loading: ref(false),
      error: ref(null),
      searchQuery: ref(''),
      showClosedCases: ref(false),
      loadData: mocks.loadData,
      getClientName: vi.fn(),
      formatDate: vi.fn(),
      sortedAndFilteredCases: ref([]),
      cases: ref([]),
    }),
  }
})

const BaseDashboardStub = defineComponent({ template: '<main><slot /></main>' })
const NewCaseModalStub = defineComponent({
  emits: ['close', 'created'],
  template: `<button
    data-testid="partial-case-created"
    @click="$emit('created', { id: 42, case_number: 'CASE-042' }, { assignmentWarning: '1 user assignment failed: unavailable' })"
  >Complete</button>`,
})
const SnackbarStub = defineComponent({
  props: { modelValue: Boolean, color: String },
  template: '<div v-if="modelValue" data-testid="notification" :data-color="color"><slot /></div>',
})
const PassthroughStub = defineComponent({ template: '<div><slot /></div>' })

describe('MainDashboard case creation', () => {
  it('refreshes the dashboard and warns when a created case has incomplete assignments', async () => {
    const wrapper = shallowMount(MainDashboard, {
      global: {
        stubs: {
          BaseDashboard: BaseDashboardStub,
          NewCaseModal: NewCaseModalStub,
          VSnackbar: SnackbarStub,
          VBtn: PassthroughStub,
        },
      },
    })
    await flushPromises()
    mocks.loadData.mockClear()

    await wrapper.get('[data-testid="partial-case-created"]').trigger('click')

    await flushPromises()
    expect(mocks.loadData).toHaveBeenCalledOnce()
    expect(mocks.selectCase).toHaveBeenCalledWith(42, { overview: true })
    const notification = wrapper.get('[data-testid="notification"]')
    expect(notification.attributes('data-color')).toBe('warning')
    expect(notification.text()).toContain(
      'Case "CASE-042" was created, but 1 user assignment failed: unavailable',
    )
    expect(notification.text()).toContain('Manage the case users to retry.')
  })
})
