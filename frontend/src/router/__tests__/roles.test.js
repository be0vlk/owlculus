import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { createAppRouter, routes } from '../index'
import api from '../../services/api'
import { useAuthStore } from '../../stores/auth'

const huntPaths = [
  ['/hunts', '/case/1/hunts'],
  ['/hunts/execution/8', '/case/1/hunts/execution/8'],
  ['/case/1/hunts', '/case/1/hunts'],
  ['/case/1/hunts/execution/8', '/case/1/hunts/execution/8'],
]
const protectedPaths = routes
  .filter((route) => route.meta?.requiresAuth)
  .map((route) => route.path.replace(':caseId', '1').replace(':id', '8'))
let adapter
let originalAdapter
let router
let pageEntered

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setActivePinia(createPinia())
  Object.assign(useAuthStore(), { isInitialized: true, setupRequired: false })
  originalAdapter = api.defaults.adapter
  adapter = vi.fn(async (config) => {
    let data
    if (config.url === '/api/cases/') data = [{ id: 1, case_number: 'ONE' }]
    else if (config.url === '/api/hunts/executions/8') data = { id: 8, case_id: 1 }
    else throw new Error(`Unexpected request: ${config.url}`)
    return { config, data, status: 200, statusText: 'OK', headers: {} }
  })
  api.defaults.adapter = adapter
  pageEntered = vi.fn()
  router = createAppRouter(
    createMemoryHistory(),
    routes.map((route) => ({
      ...route,
      // Layout rendering is outside the guard contract; retain the public route metadata.
      component: route.component ? { template: '<div />' } : undefined,
      beforeEnter: (to) => pageEntered(to.path),
    })),
  )
})

afterEach(() => {
  api.defaults.adapter = originalAdapter
  router.options.history.destroy()
  localStorage.clear()
  sessionStorage.clear()
})

function signIn(role) {
  Object.assign(useAuthStore(), { isAuthenticated: true, user: { id: 7, role } })
  localStorage.setItem('access_token', 'current-session')
}

describe('public role restrictions after setup', () => {
  it.each(protectedPaths)(
    'redirects unauthenticated %s to login before protected work',
    async (path) => {
      await router.push(path)

      expect(router.currentRoute.value.path).toBe('/login')
      expect(pageEntered).not.toHaveBeenCalledWith(path)
      expect(adapter).not.toHaveBeenCalled()
    },
  )

  it.each(
    ['Admin', 'Investigator', 'Analyst'].flatMap((role) =>
      ['/admin', '/clients'].map((path) => [role, path]),
    ),
  )('%s directly navigating to %s respects admin access', async (role, path) => {
    signIn(role)
    await router.push(path)

    expect(router.currentRoute.value.path).toBe(role === 'Admin' ? path : '/cases')
    if (role === 'Admin') expect(pageEntered).toHaveBeenCalledWith(path)
    else expect(pageEntered).not.toHaveBeenCalledWith(path)
    expect(adapter.mock.calls.every(([config]) => config.url === '/api/cases/')).toBe(true)
  })

  it.each(
    ['Admin', 'Investigator', 'Analyst'].flatMap((role) =>
      huntPaths.map(([path, canonical]) => [role, path, canonical]),
    ),
  )('%s directly navigating to %s respects Hunt access', async (role, path, canonical) => {
    signIn(role)
    await router.push(path)

    expect(router.currentRoute.value.path).toBe(role === 'Analyst' ? '/cases' : canonical)
    if (role === 'Analyst') {
      expect(pageEntered).not.toHaveBeenCalledWith(path)
      expect(pageEntered).not.toHaveBeenCalledWith(canonical)
      expect(adapter.mock.calls.every(([config]) => config.url === '/api/cases/')).toBe(true)
    } else {
      expect(pageEntered).toHaveBeenCalledWith(canonical)
      if (path.includes('execution')) {
        expect(adapter).toHaveBeenCalledWith(
          expect.objectContaining({ url: '/api/hunts/executions/8' }),
        )
      }
    }
  })
})
