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
