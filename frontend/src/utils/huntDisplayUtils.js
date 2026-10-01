/**
 * Hunt display utilities for extracting meaningful information from hunt executions
 */

const parameterPriority = {
  domain: ['domain', 'hostname', 'url'],
  person: ['username', 'email', 'full_name', 'first_name', 'last_name'],
  company: ['company_name', 'organization', 'org_name', 'name'],
  ip: ['ip_address', 'ip', 'host'],
  phone: ['phone_number', 'phone'],
  email: ['email', 'email_address'],
  general: ['target', 'query', 'search_term'],
}

/**
 * Extract display-friendly parameter value from hunt initial_parameters
 * @param {Object} initialParameters - The initial_parameters object from hunt execution
 * @param {string} huntCategory - The hunt category (domain, person, company, etc.)
 * @returns {string} Display-friendly parameter value or empty string
 */
export function extractHuntTargetDisplay(initialParameters, huntCategory) {
  if (!initialParameters || typeof initialParameters !== 'object') {
    return ''
  }

  // First non-blank string value among the given keys
  const pick = (keys) => {
    for (const key of keys) {
      const value = initialParameters[key]
      if (value && typeof value === 'string' && value.trim()) return value.trim()
    }
    return ''
  }

  return (
    pick(parameterPriority[huntCategory] || parameterPriority.general) ||
    pick(['domain', 'username', 'email', 'target', 'query', 'search', 'name']) ||
    pick(Object.keys(initialParameters).filter((key) => key !== 'save_to_case'))
  )
}

/**
 * Format hunt execution display name with target parameter
 * @param {string} huntDisplayName - The hunt's display name
 * @param {Object} initialParameters - The initial_parameters object
 * @param {string} huntCategory - The hunt category
 * @returns {string} Formatted display name with target
 */
export function formatHuntExecutionTitle(huntDisplayName, initialParameters, huntCategory) {
  const target = extractHuntTargetDisplay(initialParameters, huntCategory)

  if (target) {
    return `${huntDisplayName} • ${target}`
  }

  return huntDisplayName
}

/**
 * Get a short target description for table display
 * @param {Object} initialParameters - The initial_parameters object
 * @param {string} huntCategory - The hunt category
 * @returns {string} Short target description
 */
export function getHuntTargetSummary(initialParameters, huntCategory) {
  const target = extractHuntTargetDisplay(initialParameters, huntCategory)

  if (!target) {
    return 'N/A'
  }

  // Truncate long values for table display
  if (target.length > 30) {
    return target.substring(0, 27) + '...'
  }

  return target
}

// Status color mapping
export const getStatusColor = (status) => {
  const statusColors = {
    pending: 'grey',
    running: 'primary',
    completed: 'success',
    partial: 'warning',
    failed: 'error',
    cancelling: 'warning',
    cancelled: 'grey',
    skipped: 'warning',
  }
  return statusColors[status] || 'grey'
}

// Status icon mapping
export const getStatusIcon = (status) => {
  const statusIcons = {
    pending: 'mdi-clock-outline',
    running: 'mdi-play',
    completed: 'mdi-check',
    partial: 'mdi-alert',
    failed: 'mdi-close',
    cancelling: 'mdi-timer-sand',
    cancelled: 'mdi-stop',
    skipped: 'mdi-skip-next',
  }
  return statusIcons[status] || 'mdi-help'
}

// Status text mapping
export const getStatusText = (status, compact = false) => {
  const statusTexts = {
    pending: 'Queued',
    running: 'Running',
    completed: 'Completed',
    partial: compact ? 'Partial' : 'Partial Success',
    failed: 'Failed',
    cancelling: 'Cancelling',
    cancelled: 'Cancelled',
    skipped: 'Skipped',
  }
  return statusTexts[status] || 'Unknown'
}

// Category icon mapping
export const getCategoryIcon = (category) => {
  const iconMap = {
    person: 'mdi-account',
    domain: 'mdi-web',
    company: 'mdi-office-building',
    ip: 'mdi-ip-network',
    phone: 'mdi-phone',
    email: 'mdi-email',
    general: 'mdi-magnify',
  }
  return iconMap[category] || iconMap.general
}

// Category color mapping
export const getCategoryColor = (category) => {
  const colorMap = {
    person: 'primary',
    domain: 'info',
    company: 'warning',
    ip: 'secondary',
    phone: 'primary-darken-1',
    email: 'error',
    general: 'secondary',
  }
  return colorMap[category] || colorMap.general
}

// Calculate and format duration
// Hunt timestamps are UTC but may arrive without a zone designator.
const parseUtc = (value) =>
  new Date(typeof value === 'string' && !/(Z|[+-]\d\d:?\d\d)$/i.test(value) ? `${value}Z` : value)

export const calculateDuration = (startTime, endTime) => {
  if (!startTime) return 'N/A'

  const end = endTime ? parseUtc(endTime) : new Date()
  const diffMs = Math.max(0, end - parseUtc(startTime))

  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)

  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes % 60}m`
  } else if (diffMinutes > 0) {
    return `${diffMinutes}m ${diffSeconds % 60}s`
  } else {
    return `${diffSeconds}s`
  }
}

// Format file size
export const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Format parameter names (snake_case to Title Case)
export const formatParameterName = (paramName) => {
  return paramName.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

// Format metadata values
export const formatMetadataValue = (value) => {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

// Get display category name
export const getDisplayCategory = (category) => {
  if (!category) return 'Other'

  // Map hunt categories to display categories (matching HuntCatalog filter logic)
  const categoryMapping = {
    person: 'Person',
    domain: 'Network',
    network: 'Network',
    company: 'Company',
    general: 'Other',
    other: 'Other',
  }

  return (
    categoryMapping[category.toLowerCase()] ||
    category.charAt(0).toUpperCase() + category.slice(1).toLowerCase()
  )
}
