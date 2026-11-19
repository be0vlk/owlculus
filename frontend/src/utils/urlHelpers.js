/**
 * Ensures a URL has a proper protocol (http:// or https://)
 * @param {string} url - The URL to format
 * @returns {string} - The URL with proper protocol
 */
export function ensureProtocol(url) {
  if (!url || typeof url !== 'string') {
    return url
  }

  if (url.match(/^https?:\/\//)) {
    return url
  }

  if (url.startsWith('//')) {
    return `https:${url}`
  }

  return `https://${url}`
}
