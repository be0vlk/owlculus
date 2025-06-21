import { ref, computed } from 'vue'
import { systemService } from '@/services/system'

export function usePluginApiKeys() {
  const apiKeyStatuses = ref({})
  const loading = ref(false)
  const error = ref(null)

  const checkPluginApiKeys = async (plugin) => {
    if (!plugin.api_key_requirements || plugin.api_key_requirements.length === 0) {
      return true
    }

    loading.value = true
    error.value = null

    try {
      const statuses = {}
      let allConfigured = true

      for (const provider of plugin.api_key_requirements) {
        const status = await systemService.checkApiKeyStatus(provider)
        statuses[provider] = status.is_configured
        if (!status.is_configured) {
          allConfigured = false
        }
      }

      apiKeyStatuses.value[plugin.name] = statuses
      return allConfigured
    } catch (err) {
      console.error('Error checking plugin API keys:', err)
      error.value = err.message
      return false
    } finally {
      loading.value = false
    }
  }

  const getMissingApiKeys = (plugin) => {
    if (!plugin.api_key_requirements || plugin.api_key_requirements.length === 0) {
      return []
    }

    const statuses = apiKeyStatuses.value[plugin.name] || {}
    return plugin.api_key_requirements.filter((provider) => !statuses[provider])
  }

  const getApiKeyWarningMessage = (plugin) => {
    const missing = getMissingApiKeys(plugin)
    if (missing.length === 0) {
      return null
    }

    const providers = missing.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(', ')
    const plural = missing.length > 1

    return `This plugin requires ${plural ? 'API keys' : 'an API key'} for: ${providers}. Please contact your administrator to configure ${plural ? 'them' : 'it'} in the system settings.`
  }

  const hasAllRequiredApiKeys = computed(() => (plugin) => {
    if (!plugin.api_key_requirements || plugin.api_key_requirements.length === 0) {
      return true
    }

    const statuses = apiKeyStatuses.value[plugin.name] || {}
    return plugin.api_key_requirements.every((provider) => statuses[provider])
  })

  return {
    apiKeyStatuses,
    loading,
    error,
    checkPluginApiKeys,
    getMissingApiKeys,
    getApiKeyWarningMessage,
    hasAllRequiredApiKeys,
  }
}
