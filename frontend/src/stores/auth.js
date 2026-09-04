import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { authService } from '../services/auth'
import { useActiveCaseStore } from './activeCase'

// Development-only state persistence to handle HMR reloads
const DEV_STATE_KEY = '__owlculus_dev_auth_state__'

const getDevPersistedState = () => {
  if (import.meta.env.DEV) {
    try {
      const saved = sessionStorage.getItem(DEV_STATE_KEY)
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  }
  return null
}

const saveDevState = (state) => {
  if (import.meta.env.DEV) {
    try {
      sessionStorage.setItem(DEV_STATE_KEY, JSON.stringify(state))
    } catch {
      // Ignore storage errors
    }
  }
}

export const useAuthStore = defineStore('auth', () => {
  // Try to restore state from development persistence
  const persistedState = getDevPersistedState()

  const user = ref(persistedState?.user || null)
  const isAuthenticated = ref(persistedState?.isAuthenticated ?? authService.isAuthenticated())
  const error = ref(persistedState?.error || null)
  // Setup status is always rechecked on page load, including development reloads.
  const isInitialized = ref(false)
  const setupRequired = ref(null)
  const initPromise = ref(null)

  const persistCurrentDevState = () => {
    saveDevState({
      user: user.value,
      isAuthenticated: isAuthenticated.value,
      isInitialized: isInitialized.value,
      setupRequired: setupRequired.value,
      error: error.value,
    })
  }

  // Initialize user data if already authenticated
  async function init() {
    // If already initialized, return immediately
    if (isInitialized.value) {
      return
    }

    // If initialization is in progress, return the existing promise
    if (initPromise.value) {
      return initPromise.value
    }

    // Start initialization
    initPromise.value = (async () => {
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

        // Refresh authentication status from localStorage
        const authStatus = authService.isAuthenticated()
        isAuthenticated.value = authStatus

        if (authStatus) {
          const userData = await authService.getCurrentUser()
          user.value = userData
        } else {
          user.value = null
        }
      } catch (err) {
        console.error('Failed to initialize user data:', err)
        // Clear authentication state on initialization failure
        user.value = null
        isAuthenticated.value = false
        authService.logout()
      } finally {
        isInitialized.value = true

        persistCurrentDevState()
      }
    })()

    return initPromise.value
  }

  async function login(username, password) {
    try {
      error.value = null
      const data = await authService.login(username, password)
      useActiveCaseStore().reset()
      isAuthenticated.value = true
      user.value = data.user

      persistCurrentDevState()

      return data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      throw err
    }
  }

  async function logout() {
    useActiveCaseStore().reset()
    authService.logout()
    user.value = null
    isAuthenticated.value = false
    // Reset initialization state to allow re-initialization
    isInitialized.value = false
    initPromise.value = null
    error.value = null

    // Clear development state persistence
    if (import.meta.env.DEV) {
      try {
        sessionStorage.removeItem(DEV_STATE_KEY)
      } catch {
        // Ignore storage errors
      }
    }
  }

  async function changePassword(passwordData) {
    try {
      await api.put('/api/users/me/password', passwordData)
    } catch (err) {
      console.error('Password change error:', err)
      throw err
    }
  }

  function completeSetup() {
    setupRequired.value = false
    user.value = null
    isAuthenticated.value = false
  }

  // Helper function to check if user is admin
  function requiresAdmin() {
    return user.value?.role === 'Admin'
  }

  // Don't auto-initialize - let the router handle it to avoid race conditions

  return {
    user,
    isAuthenticated,
    error,
    login,
    logout,
    init,
    isInitialized,
    initPromise,
    setupRequired,
    requiresAdmin,
    changePassword,
    completeSetup,
  }
})
