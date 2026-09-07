export function useEntityValidation() {
  const domainRule = (value) => {
    if (!value) return 'Domain is required'
    const invalid = 'Please enter a valid domain name'
    const text = value.trim()
    // URL supplies the browser's IDNA conversion; validate bare labels separately.
    if (
      /[\s/\\:@?#%_[\]]/u.test(text) ||
      [...text].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)
    )
      return invalid
    try {
      // A suffix prevents URL's IPv4 coercion for numeric final labels.
      // The backend remains authoritative for contextual IDNA validity.
      const bare = text.replace(/[.\u3002\uff0e\uff61]$/, '')
      const host = new URL(`https://${bare}.invalid`).hostname.slice(0, -8)
      return (
        (host.length <= 253 &&
          host
            .split('.')
            .every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label))) ||
        invalid
      )
    } catch {
      return invalid
    }
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
