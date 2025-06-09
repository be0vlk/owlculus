import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'
import { authService } from '../services/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = ref(authService.isAuthenticated())
  const error = ref(null)
  const isInitialized = ref(false)
  const initPromise = ref(null)

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
      if (isAuthenticated.value) {
        try {
          const userData = await authService.getCurrentUser()
          user.value = userData
        } catch (err) {
          console.error('Failed to initialize user data:', err)
          // If we fail to get user data, we should logout
          logout()
        }
      }
      isInitialized.value = true
    })()

    return initPromise.value
  }

  async function login(username, password) {
    try {
      error.value = null
      const data = await authService.login(username, password)
      isAuthenticated.value = true
      user.value = data.user
      return data
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed'
      throw err
    }
  }

  async function logout() {
    authService.logout()
    user.value = null
    isAuthenticated.value = false
  }

  async function changePassword(passwordData) {
    try {
      await api.put('/api/users/me/password', passwordData)
    } catch (err) {
      console.error('Password change error:', err)
      throw err
    }
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
    requiresAdmin,
    changePassword,
  }
})
