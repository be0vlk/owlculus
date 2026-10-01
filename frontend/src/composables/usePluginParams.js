import { ipAddressRule } from '@/utils/ipAddress'
import { reactive, computed, watch } from 'vue'

/**
 * Enhanced composable for standardized plugin parameter management
 */
export function usePluginParamsAdvanced(props, emit, config = {}) {
  const { parameterDefaults = {}, customUpdateLogic = null } = config

  const pluginDescription = computed(() => {
    return props.parameters?.description || ''
  })

  const localParams = reactive({
    ...parameterDefaults,
    ...Object.fromEntries(
      Object.keys(parameterDefaults).map((key) => [
        key,
        props.modelValue[key] ?? parameterDefaults[key],
      ]),
    ),
  })

  const updateParams = () => {
    const updatedValue = {
      ...props.modelValue,
      ...localParams,
    }

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

  return {
    pluginDescription,
    localParams,
    updateParams,
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

  const ipRule = ipAddressRule

  return {
    emailRule,
    domainRule,
    ipRule,
  }
}
