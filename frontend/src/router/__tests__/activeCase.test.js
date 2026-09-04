import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { flushPromises } from '@vue/test-utils'
import { createAppRouter, routes } from '../index'
import { useAuthStore } from '../../stores/auth'
import { useActiveCaseStore, ACTIVE_CASE_STORAGE_KEY } from '../../stores/activeCase'
import taskService from '../../services/task'
import { caseService } from '../../services/case'

vi.mock('../../services/case', () => ({ caseService: { getCases: vi.fn() } }))
vi.mock('../../services/task', () => ({ default: { getTask: vi.fn() } }))
const cases = [
  { id: 1, case_number: 'ONE', status: 'Closed', created_at: '2025-01-01' },
  { id: 2, case_number: 'TWO', status: 'Open', created_at: '2026-01-01' },
]
let router
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setActivePinia(createPinia())
  Object.assign(useAuthStore(), {
    isInitialized: true,
    isAuthenticated: true,
    user: { id: 1, role: 'Admin' },
  })
  caseService.getCases.mockResolvedValue(cases)
  router = createAppRouter(
    createMemoryHistory(),
    routes.map((route) => ({
      ...route,
      component: route.component ? { template: '<div />' } : undefined,
    })),
  )
})

it('follows a direct URL and switches case preserving compatible query parameters', async () => {
  localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, '2')
  await router.push('/case/1?tab=notes&entity=99')
  const store = useActiveCaseStore()
  expect(store.activeCaseId).toBe(1)
  await store.select(2)
  expect(router.currentRoute.value.fullPath).toBe('/case/2?tab=notes')
  expect(store.activeCaseId).toBe(2)
})

it('preserves selection on independent pages and selects before opening an overview', async () => {
  await router.push('/case/1')
  for (const path of ['/cases', '/clients', '/admin', '/settings']) {
    await router.push(path)
    expect(useActiveCaseStore().activeCaseId).toBe(1)
  }
  await useActiveCaseStore().select(2)
  expect(router.currentRoute.value.path).toBe('/case/2')
})

it('follows browser back and forward', async () => {
  await router.push('/case/1')
  await router.push('/case/2')
  const navigate = (action) =>
    new Promise((resolve) => {
      const remove = router.afterEach(() => {
        remove()
        resolve()
      })
      action()
    })
  await navigate(() => router.back())
  expect(useActiveCaseStore().activeCaseId).toBe(1)
  await navigate(() => router.forward())
  expect(useActiveCaseStore().activeCaseId).toBe(2)
})

it('replaces unavailable routes and recovers when membership refresh removes the active case', async () => {
  await router.push('/case/999?tab=notes')
  expect(router.currentRoute.value.fullPath).toBe('/case/2?tab=notes')
  expect(useActiveCaseStore().notification).toContain('unavailable')
  caseService.getCases.mockResolvedValue([cases[0]])
  await useActiveCaseStore().refresh()
  expect(router.currentRoute.value.fullPath).toBe('/case/1?tab=notes')
  caseService.getCases.mockResolvedValue([])
  await useActiveCaseStore().refresh()
  expect(router.currentRoute.value.path).toBe('/cases')
  await router.push('/plugins')
  expect(router.currentRoute.value.path).toBe('/cases')
})

it('recovers from a detail endpoint rejecting a case even when the list is stale', async () => {
  await router.push('/case/2')
  await useActiveCaseStore().recoverUnavailable(2)
  expect(router.currentRoute.value.path).toBe('/case/1')
})

it('resets authorization context at logout, preserving only the browser preference', async () => {
  await router.push('/case/1')
  await useAuthStore().logout()
  expect(useActiveCaseStore().activeCaseId).toBeNull()
  expect(useActiveCaseStore().accessibleCases).toEqual([])
  expect(localStorage.getItem(ACTIVE_CASE_STORAGE_KEY)).toBe('1')
})

it('waits for an accessible-case refresh before honoring a new case URL', async () => {
  await router.push('/case/1')
  let finish
  caseService.getCases.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const refresh = useActiveCaseStore().refresh()
  const navigation = router.push('/case/2?tab=notes')
  await flushPromises()
  finish(cases)
  await Promise.all([refresh, navigation])
  expect(router.currentRoute.value.fullPath).toBe('/case/2?tab=notes')
  expect(useActiveCaseStore().activeCaseId).toBe(2)
})

it('opens the Cases empty state when the last accessible case disappears on a global page', async () => {
  await router.push('/settings')
  caseService.getCases.mockResolvedValue([])
  await useActiveCaseStore().refresh()
  expect(router.currentRoute.value.path).toBe('/cases')
  expect(useActiveCaseStore().activeCaseId).toBeNull()
  expect(useActiveCaseStore().notification).toContain('No accessible cases remain')
})

it('redirects legacy tasks and preserves the task dashboard when switching cases', async () => {
  await router.push('/tasks?filter=me')
  expect(router.currentRoute.value.fullPath).toBe('/case/2/tasks?filter=me')
  await useActiveCaseStore().select(1)
  expect(router.currentRoute.value.fullPath).toBe('/case/1/tasks?filter=me')
})

for (const path of ['/tasks/8', '/case/2/tasks/8']) {
  it(`reconciles authorized task ownership for ${path}`, async () => {
    taskService.getTask.mockResolvedValue({ id: 8, case_id: 1 })
    await router.push(path)
    expect(router.currentRoute.value.path).toBe('/case/1/tasks/8')
    expect(useActiveCaseStore().activeCaseId).toBe(1)
  })
}

it('sends inaccessible task links to Cases', async () => {
  taskService.getTask.mockRejectedValue({ response: { status: 403 } })
  await router.push('/tasks/8')
  expect(router.currentRoute.value.path).toBe('/cases')
})

it('does not request a legacy task when there are no accessible cases', async () => {
  taskService.getTask.mockClear()
  caseService.getCases.mockResolvedValue([])
  await router.push('/tasks/8')
  expect(router.currentRoute.value.path).toBe('/cases')
  expect(taskService.getTask).not.toHaveBeenCalled()
})
