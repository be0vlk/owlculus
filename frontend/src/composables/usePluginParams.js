import { ref, reactive, computed, watch, onMounted } from 'vue'

export function usePluginParams(initialParams = {}, emit) {
  const localParams = ref({ ...initialParams })

  const updateParams = () => {
    emit('update:params', localParams.value)
  }

  const resetParams = () => {
    localParams.value = { ...initialParams }
    updateParams()
  }

  const setParam = (key, value) => {
    localParams.value[key] = value
    updateParams()
  }

  return {
    localParams,
    updateParams,
    resetParams,
    setParam,
  }
}

/**
 * Enhanced composable for standardized plugin parameter management
 * Eliminates boilerplate code duplication across plugin parameter components
 */
export function usePluginParamsAdvanced(props, emit, config = {}) {
  const {
    parameterDefaults = {},
    apiKeyRequirements = null,
    onApiKeyCheck = null,
    customUpdateLogic = null,
  } = config

  // Plugin description from backend
  const pluginDescription = computed(() => {
    return props.parameters?.description || ''
  })

  // Local parameter state for plugin-specific params
  const localParams = reactive({
    ...parameterDefaults,
    ...Object.fromEntries(
      Object.keys(parameterDefaults).map((key) => [
        key,
        props.modelValue[key] ?? parameterDefaults[key],
      ]),
    ),
  })

  // API key state (if plugin requires API keys)
  const missingApiKeys = ref([])
  const apiKeyError = ref(null)

  // Emit parameter updates for plugin-specific params
  const updateParams = () => {
    const updatedValue = {
      ...props.modelValue,
      ...localParams,
    }

    // Allow custom update logic if provided
    if (customUpdateLogic) {
      customUpdateLogic(updatedValue, localParams)
    }

    emit('update:modelValue', updatedValue)
  }

  // Watch for external changes to modelValue
  watch(
    () => props.modelValue,
    (newValue) => {
      Object.assign(localParams, {
        ...Object.fromEntries(
          Object.keys(parameterDefaults).map((key) => [
            key,
            newValue[key] ?? parameterDefaults[key],
          ]),
        ),
      })
    },
    { deep: true },
  )

  // API key checking (if configured)
  const checkApiKeys = async () => {
    if (!apiKeyRequirements || !onApiKeyCheck) return

    try {
      const result = await onApiKeyCheck(apiKeyRequirements)
      missingApiKeys.value = result.missing || []
      apiKeyError.value = result.error || null
    } catch (error) {
      console.error('Failed to check API keys:', error)
      apiKeyError.value = 'Failed to validate API keys'
    }
  }

  // Initialize API key checking on mount if configured
  onMounted(() => {
    if (apiKeyRequirements && props.parameters.api_key_requirements) {
      checkApiKeys()
    }
  })

  return {
    // Computed
    pluginDescription,

    // State
    localParams,
    missingApiKeys,
    apiKeyError,

    // Methods
    updateParams,
    checkApiKeys,
  }
}

export function usePluginValidation() {
  const emailRule = (value) => {
    if (!value) return 'Email is required'
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailPattern.test(value) || 'Please enter a valid email address'
  }

  const domainRule = (value) => {
    if (!value) return 'Domain is required'
    const domainPattern = /^[a-zA-Z0-9][a-zA-Z0-9-_]*\.{1}[a-zA-Z]{2,}$/
    return domainPattern.test(value) || 'Please enter a valid domain name'
  }

  const ipRule = (value) => {
    if (!value) return 'IP address is required'
    const ipPattern =
      /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
    return ipPattern.test(value) || 'Please enter a valid IP address'
  }

  return {
    emailRule,
    domainRule,
    ipRule,
  }
}

/**
 * Configuration helper for common parameter types
 */
export const pluginParamConfigs = {
  // Domain-based plugins
  domain: (defaultDomain = '') => ({
    domain: defaultDomain,
  }),

  // Domain with concurrency
  domainWithConcurrency: (defaultDomain = '', defaultConcurrency = 5) => ({
    domain: defaultDomain,
    concurrency: defaultConcurrency,
  }),

  // Domain with SecurityTrails option
  domainWithSecurityTrails: (defaultDomain = '', defaultConcurrency = 5) => ({
    domain: defaultDomain,
    concurrency: defaultConcurrency,
    use_securitytrails: false,
  }),

  // Email-based plugins
  email: (defaultEmail = '') => ({
    email: defaultEmail,
  }),

  // IP-based plugins
  ip: (defaultIp = '') => ({
    ip_address: defaultIp,
  }),

  // Search-based plugins
  searchQuery: (defaultQuery = '') => ({
    query: defaultQuery,
  }),

  // Multiple search types
  multiSearch: (searchTypes = [], defaultType = '') => ({
    search_type: defaultType,
    query: '',
  }),
}
