import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

export function useDashboardState(loadDataFunction = null) {
  const router = useRouter()
  const authStore = useAuthStore()

  const loading = ref(false)
  const error = ref(null)
  const refreshing = ref(false)

  const checkAuth = () => {
    if (!authStore.isAuthenticated) {
      router.push('/login')
      return false
    }
    return true
  }

  const handleError = (err, context = 'operation') => {
    console.error(`Dashboard ${context} error:`, err)
    error.value = `Failed to ${context}. Please try again.`
    loading.value = false
    refreshing.value = false
  }

  const loadData = async (showLoading = true) => {
    if (!checkAuth()) return

    try {
      if (showLoading) {
        loading.value = true
      } else {
        refreshing.value = true
      }

      error.value = null

      if (loadDataFunction) {
        await loadDataFunction()
      }

      loading.value = false
      refreshing.value = false
    } catch (err) {
      handleError(err, 'load data')
    }
  }

  const refresh = async () => {
    await loadData(false)
  }

  const withErrorHandling = async (operation, context = 'operation') => {
    try {
      error.value = null
      await operation()
    } catch (err) {
      handleError(err, context)
      throw err
    }
  }

  const setLoading = (state) => {
    loading.value = state
    if (state) {
      error.value = null
    }
  }

  const setError = (message) => {
    error.value = message
    loading.value = false
    refreshing.value = false
  }

  const clearError = () => {
    error.value = null
  }

  if (loadDataFunction) {
    onMounted(() => {
      loadData()
    })
  }

  return {
    loading,
    error,
    refreshing,
    loadData,
    refresh,
    handleError,
    withErrorHandling,
    setLoading,
    setError,
    clearError,
    checkAuth,
  }
}
