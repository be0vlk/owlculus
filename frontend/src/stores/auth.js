import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { authService } from '../services/auth'
import { useActiveCaseStore } from './activeCase'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = ref(authService.isAuthenticated())
  // Setup status is always rechecked on page load.
  const isInitialized = ref(false)
  const setupRequired = ref(null)
  // Router and App both call init(); share the in-flight run.
  let initPromise = null

  async function init() {
    if (isInitialized.value) return
    initPromise ??= (async () => {
      try {
        try {
          const setupStatus = await authService.getSetupStatus()
          setupRequired.value = setupStatus.setup_required
        } catch (err) {
          console.error('Failed to retrieve setup status:', err)
          setupRequired.value = false
        }

        if (setupRequired.value) {
          authService.logout()
          user.value = null
          isAuthenticated.value = false
          return
        }

        isAuthenticated.value = authService.isAuthenticated()
        user.value = isAuthenticated.value ? await authService.getCurrentUser() : null
      } catch (err) {
        console.error('Failed to initialize user data:', err)
        user.value = null
        isAuthenticated.value = false
        authService.logout()
      } finally {
        isInitialized.value = true
      }
    })()
    return initPromise
  }

  async function login(username, password) {
    const data = await authService.login(username, password)
    useActiveCaseStore().reset()
    isAuthenticated.value = true
    user.value = data.user
    return data
  }

  async function logout() {
    useActiveCaseStore().reset()
    authService.logout()
    user.value = null
    isAuthenticated.value = false
    isInitialized.value = false
    initPromise = null
  }

  async function changePassword(passwordData) {
    await api.put('/api/users/me/password', passwordData)
    await logout()
  }

  function completeSetup() {
    setupRequired.value = false
    user.value = null
    isAuthenticated.value = false
  }

  function requiresAdmin() {
    return user.value?.role === 'Admin'
  }

  return {
    user,
    isAuthenticated,
    login,
    logout,
    init,
    isInitialized,
    setupRequired,
    requiresAdmin,
    changePassword,
    completeSetup,
  }
})
