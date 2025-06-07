import { ref } from 'vue'

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
