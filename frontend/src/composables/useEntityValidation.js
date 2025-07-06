export function useEntityValidation() {
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

  const isFormValid = (entityType, data) => {
    if (!entityType) return false

    switch (entityType) {
      case 'person':
        return data.first_name || data.last_name
      case 'company':
        return data.name
      case 'domain':
        return data.domain && domainRule(data.domain) === true
      case 'ip_address':
        return data.ip_address && ipRule(data.ip_address) === true
      case 'vehicle':
        return data.make && data.model
      default:
        return false
    }
  }

  return {
    domainRule,
    ipRule,
    isFormValid,
  }
}
