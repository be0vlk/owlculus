export const entityIdentityGuidance = {
  person: 'Provide a name, email, phone, employer, or HTTP(S) profile reference.',
  vehicle: 'Provide a VIN, license plate, or both make and model.',
}

export const supportedProfile = (value) => {
  if (
    typeof value !== 'string' ||
    !/^https?:\/\//i.test(value.trim()) ||
    /[\s\\]/u.test(value.trim())
  )
    return false
  try {
    return Boolean(new URL(value.trim()).hostname)
  } catch {
    return false
  }
}
const nonblank = (value) => typeof value === 'string' && value.trim().length > 0

export const emailRule = (value) => {
  if (!value) return 'Email is required'
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || 'Please enter a valid email address'
}

export const domainRule = (value) => {
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
        host.split('.').every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label))) ||
      invalid
    )
  } catch {
    return invalid
  }
}

/** Validate complete literals; the backend owns canonical persistence. */
export const ipRule = (value) => {
  if (!value) return 'IP address is required'
  const invalid = 'Please enter a valid IPv4 or IPv6 address'
  const text = value.trim()
  if (text.includes(':')) {
    if (!/^[0-9a-f:.]+$/i.test(text)) return invalid
    try {
      // The browser URL parser validates an entire bracketed IPv6 literal.
      return new URL(`http://[${text}]/`).hostname.startsWith('[') || invalid
    } catch {
      return invalid
    }
  }
  const parts = text.split('.')
  return (
    (parts.length === 4 &&
      parts.every((part) => /^(0|[1-9][0-9]{0,2})$/.test(part) && Number(part) <= 255)) ||
    invalid
  )
}

export const isFormValid = (entityType, data) => {
  switch (entityType) {
    case 'person':
      return (
        [data.first_name, data.last_name, data.email, data.employer].some(nonblank) ||
        /^\+?[0-9]+$/.test((data.phone || '').trim().replace(/[ ().-]/g, '')) ||
        [...Object.values(data.social_media || {}), ...(data.usernames || [])].some(
          supportedProfile,
        )
      )
    case 'company':
      return data.name
    case 'domain':
      return data.domain && domainRule(data.domain) === true
    case 'ip_address':
      return data.ip_address && ipRule(data.ip_address) === true
    case 'vehicle':
      return (
        nonblank(data.vin) ||
        nonblank(data.license_plate) ||
        (nonblank(data.make) && nonblank(data.model))
      )
    default:
      return false
  }
}
