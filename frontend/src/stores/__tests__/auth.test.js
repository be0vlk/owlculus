import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { authService } from '../../services/auth'
import { useAuthStore } from '../auth'

vi.mock('../../services/auth')

describe('auth store setup initialization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('clears stale authentication and skips the current user lookup when setup is required', async () => {
    authService.getSetupStatus.mockResolvedValue({ setup_required: true })
    authService.isAuthenticated.mockReturnValue(true)

    const store = useAuthStore()
    await store.init()

    expect(authService.getSetupStatus).toHaveBeenCalledOnce()
    expect(authService.logout).toHaveBeenCalledOnce()
    expect(authService.getCurrentUser).not.toHaveBeenCalled()
    expect(store.setupRequired).toBe(true)
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(store.isInitialized).toBe(true)
  })

  it('loads the current user only after setup is known to be complete', async () => {
    const currentUser = { id: 7, username: 'owl_admin', role: 'Admin' }
    authService.getSetupStatus.mockResolvedValue({ setup_required: false })
    authService.isAuthenticated.mockReturnValue(true)
    authService.getCurrentUser.mockResolvedValue(currentUser)

    const store = useAuthStore()
    await store.init()

    expect(authService.getSetupStatus.mock.invocationCallOrder[0]).toBeLessThan(
      authService.getCurrentUser.mock.invocationCallOrder[0],
    )
    expect(store.setupRequired).toBe(false)
    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(currentUser)
  })

  it('continues the existing authentication flow when setup status fails', async () => {
    const currentUser = { id: 8, username: 'investigator', role: 'Investigator' }
    authService.getSetupStatus.mockRejectedValue(new Error('status unavailable'))
    authService.isAuthenticated.mockReturnValue(true)
    authService.getCurrentUser.mockResolvedValue(currentUser)

    const store = useAuthStore()
    await store.init()

    expect(authService.getCurrentUser).toHaveBeenCalledOnce()
    expect(store.setupRequired).toBe(false)
    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(currentUser)
  })

  it('marks setup complete without authenticating the new administrator', async () => {
    authService.getSetupStatus.mockResolvedValue({ setup_required: true })
    authService.isAuthenticated.mockReturnValue(false)

    const store = useAuthStore()
    await store.init()
    store.completeSetup()

    expect(store.setupRequired).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(authService.login).not.toHaveBeenCalled()
  })
})

vi.mock('../../services/api', () => ({ default: { put: vi.fn() } }))

it.each([true, false])(
  'clears session and case context only after successful password change: %s',
  async (succeeds) => {
    const { default: api } = await import('../../services/api')
    const { useActiveCaseStore } = await import('../activeCase')
    setActivePinia(createPinia())
    vi.clearAllMocks()
    sessionStorage.clear()
    const store = useAuthStore()
    const cases = useActiveCaseStore()
    store.user = { id: 1, role: 'Investigator' }
    store.isAuthenticated = true
    cases.accessibleCases = [{ id: 5 }]
    cases.initialized = true
    cases.resolve(5)
    if (succeeds) {
      api.put.mockResolvedValue({ data: { id: 1 } })
      await store.changePassword({ current_password: 'old', new_password: 'new' })
      expect(store.isAuthenticated).toBe(false)
      expect(store.user).toBeNull()
      expect(cases.accessibleCases).toEqual([])
      expect(cases.activeCaseId).toBeNull()
      expect(authService.logout).toHaveBeenCalledOnce()
    } else {
      api.put.mockRejectedValue(new Error('Rejected change'))
      await expect(store.changePassword({})).rejects.toThrow('Rejected change')
      expect(store.isAuthenticated).toBe(true)
      expect(store.user.id).toBe(1)
      expect(cases.activeCaseId).toBe(5)
      expect(authService.logout).not.toHaveBeenCalled()
    }
  },
)
