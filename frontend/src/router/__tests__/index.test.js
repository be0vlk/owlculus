import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { authService } from '../../services/auth'
import { useAuthStore } from '../../stores/auth'
import { createAppRouter, routes } from '../index'

vi.mock('../../services/auth', () => ({
  authService: {
    getSetupStatus: vi.fn(),
    getCurrentUser: vi.fn(),
    isAuthenticated: vi.fn(),
    logout: vi.fn(),
    login: vi.fn(),
  },
}))

describe('setup-aware routing', () => {
  const testRoutes = routes.map((route) => ({
    ...route,
    component: route.component ? { template: '<div />' } : undefined,
  }))

  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
    authService.isAuthenticated.mockReturnValue(false)
    authService.getSetupStatus.mockResolvedValue({ setup_required: false })
  })

  it.each(['/cases', '/login'])(
    'redirects %s to setup when the installation has no users',
    async (destination) => {
      authService.getSetupStatus.mockResolvedValue({ setup_required: true })
      const router = createAppRouter(createMemoryHistory(), testRoutes)

      await router.push(destination)

      expect(router.currentRoute.value.path).toBe('/setup')
    },
  )

  it('redirects setup to login when setup is complete', async () => {
    const store = useAuthStore()
    expect(store.isInitialized).toBe(false)
    expect(store.setupRequired).toBeNull()
    const router = createAppRouter(createMemoryHistory(), testRoutes)

    await router.push('/setup')

    expect(store.setupRequired).toBe(false)
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redirects an authenticated visitor from setup to cases', async () => {
    authService.isAuthenticated.mockReturnValue(true)
    authService.getCurrentUser.mockResolvedValue({ id: 1, role: 'Admin' })
    const store = useAuthStore()
    const router = createAppRouter(createMemoryHistory(), testRoutes)

    await router.push('/setup')

    expect(store.setupRequired).toBe(false)
    expect(store.isAuthenticated).toBe(true)
    expect(router.currentRoute.value.path).toBe('/cases')
  })

  it('uses the existing login redirect when setup status cannot be loaded', async () => {
    authService.getSetupStatus.mockRejectedValue(new Error('unavailable'))
    const router = createAppRouter(createMemoryHistory(), testRoutes)

    await router.push('/cases')

    expect(router.currentRoute.value.path).toBe('/login')
  })
})
