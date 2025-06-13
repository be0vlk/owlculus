import { ref, computed } from 'vue'
import api from '@/services/api'

export function useApiKeys() {
  // State
  const apiKeys = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const deleting = ref(false)
  const error = ref(null)

  // Form state
  const showAddDialog = ref(false)
  const showEditDialog = ref(false)
  const editingProvider = ref(null)
  const newKeyForm = ref({
    provider: '',
    name: '',
    api_key: '',
  })
  const editKeyForm = ref({
    provider: '',
    name: '',
    api_key: '',
  })

  // Common API providers
  const commonProviders = [
    { text: 'OpenAI', value: 'openai', icon: 'mdi-robot' },
    { text: 'People Data Labs', value: 'people_data_labs', icon: 'mdi-account-group' },
    { text: 'Shodan', value: 'shodan', icon: 'mdi-radar' },
    { text: 'Custom', value: 'custom', icon: 'mdi-plus' },
  ]

  // Computed properties
  const sortedApiKeys = computed(() => {
    return [...apiKeys.value].sort((a, b) => a.provider.localeCompare(b.provider))
  })

  const isFormValid = computed(() => {
    if (showAddDialog.value) {
      const form = newKeyForm.value
      return form.provider && form.api_key && form.name
    } else {
      const form = editKeyForm.value
      return form.name // API key is optional for editing
    }
  })

  // Validation functions
  const validateProvider = (value) => {
    if (!value) return 'Provider is required'
    if (!/^[a-z0-9_-]+$/i.test(value)) {
      return 'Provider must contain only letters, numbers, underscores, and hyphens'
    }
    return true
  }

  const validateApiKey = (value) => {
    if (!value) return 'API key is required'
    if (value.length < 8) return 'API key must be at least 8 characters'
    return true
  }

  const validateName = (value) => {
    if (!value) return 'Name is required'
    return true
  }

  // Methods
  const loadApiKeys = async () => {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/api/admin/configuration/api-keys')

      // Transform the response to match our expected format
      const keyData = response.data
      apiKeys.value = Object.entries(keyData).map(([provider, data]) => ({
        provider,
        name: data.name || `${provider.charAt(0).toUpperCase() + provider.slice(1)} API`,
        is_configured: data.is_configured !== false,
        created_at: data.created_at,
        masked_key: '••••••••••••',
      }))
    } catch (err) {
      console.error('Error loading API keys:', err)
      error.value = 'Failed to load API keys'
      apiKeys.value = []
    } finally {
      loading.value = false
    }
  }

  const addApiKey = async () => {
    if (!isFormValid.value) return false

    saving.value = true
    try {
      const payload = {
        api_key: newKeyForm.value.api_key,
        name: newKeyForm.value.name,
      }

      await api.put(`/api/admin/configuration/api-keys/${newKeyForm.value.provider}`, payload)

      await loadApiKeys()
      resetNewKeyForm()
      showAddDialog.value = false

      return true
    } catch (err) {
      console.error('Error adding API key:', err)
      throw new Error(err.response?.data?.detail || 'Failed to add API key')
    } finally {
      saving.value = false
    }
  }

  const updateApiKey = async () => {
    if (!isFormValid.value) return false

    saving.value = true
    try {
      const payload = {
        name: editKeyForm.value.name,
      }

      // Only include API key if provided
      if (editKeyForm.value.api_key) {
        payload.api_key = editKeyForm.value.api_key
      }

      await api.put(`/api/admin/configuration/api-keys/${editKeyForm.value.provider}`, payload)

      await loadApiKeys()
      showEditDialog.value = false

      return true
    } catch (err) {
      console.error('Error updating API key:', err)
      throw new Error(err.response?.data?.detail || 'Failed to update API key')
    } finally {
      saving.value = false
    }
  }

  const deleteApiKey = async (provider) => {
    deleting.value = true
    try {
      await api.delete(`/api/admin/configuration/api-keys/${provider}`)
      await loadApiKeys()
      return true
    } catch (err) {
      console.error('Error deleting API key:', err)
      throw new Error(err.response?.data?.detail || 'Failed to delete API key')
    } finally {
      deleting.value = false
    }
  }

  const openAddDialog = () => {
    resetNewKeyForm()
    showAddDialog.value = true
  }

  const openEditDialog = (apiKey) => {
    editingProvider.value = apiKey.provider
    editKeyForm.value = {
      provider: apiKey.provider,
      name: apiKey.name,
      api_key: '', // Don't pre-fill the API key for security
    }
    showEditDialog.value = true
  }

  const closeAddDialog = () => {
    showAddDialog.value = false
    resetNewKeyForm()
  }

  const closeEditDialog = () => {
    showEditDialog.value = false
    editingProvider.value = null
    editKeyForm.value = {
      provider: '',
      name: '',
      api_key: '',
    }
  }

  const resetNewKeyForm = () => {
    newKeyForm.value = {
      provider: '',
      name: '',
      api_key: '',
    }
  }

  const handleProviderChange = (provider, form) => {
    if (provider && provider !== 'custom') {
      const providerInfo = commonProviders.find((p) => p.value === provider)
      if (providerInfo && !form.name) {
        form.name = `${providerInfo.text} API`
      }
    }
  }

  const maskApiKey = (key) => {
    if (!key) return '••••••••'
    if (key.length <= 8) return '••••••••'
    return key.substring(0, 4) + '••••••••' + key.substring(key.length - 4)
  }

  const getProviderIcon = (provider) => {
    const providerInfo = commonProviders.find((p) => p.value === provider)
    return providerInfo?.icon || 'mdi-key'
  }

  const getProviderDisplayName = (provider) => {
    const providerInfo = commonProviders.find((p) => p.value === provider)
    return providerInfo?.text || provider.charAt(0).toUpperCase() + provider.slice(1)
  }

  return {
    // State
    apiKeys,
    loading,
    saving,
    deleting,
    error,
    showAddDialog,
    showEditDialog,
    editingProvider,
    newKeyForm,
    editKeyForm,

    // Constants
    commonProviders,

    // Computed
    sortedApiKeys,
    isFormValid,

    // Validation
    validateProvider,
    validateApiKey,
    validateName,

    // Methods
    loadApiKeys,
    addApiKey,
    updateApiKey,
    deleteApiKey,
    openAddDialog,
    openEditDialog,
    closeAddDialog,
    closeEditDialog,
    resetNewKeyForm,
    handleProviderChange,
    maskApiKey,
    getProviderIcon,
    getProviderDisplayName,
  }
}
