/**
 * Ensures a URL has a proper protocol (http:// or https://)
 * @param {string} url - The URL to format
 * @returns {string} - The URL with proper protocol
 */
export function ensureProtocol(url) {
  if (!url || typeof url !== 'string') {
    return url
  }

  // If URL already has a protocol, return as is
  if (url.match(/^https?:\/\//)) {
    return url
  }

  // If URL starts with '//', add https:
  if (url.startsWith('//')) {
    return `https:${url}`
  }

  // Otherwise, add https:// prefix
  return `https://${url}`
}

/**
 * Validates if a string looks like a URL
 * @param {string} url - The string to validate
 * @returns {boolean} - True if it looks like a URL
 */
export function isValidUrl(url) {
  if (!url || typeof url !== 'string') {
    return false
  }

  try {
    const urlObj = new URL(ensureProtocol(url))
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:'
  } catch {
    return false
  }
}
