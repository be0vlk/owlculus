/**
 * Hunt display utilities for extracting meaningful information from hunt executions
 */

/**
 * Extract display-friendly parameter value from hunt initial_parameters
 * @param {Object} initialParameters - The initial_parameters object from hunt execution
 * @param {string} huntCategory - The hunt category (domain, person, company, etc.)
 * @returns {string} Display-friendly parameter value or empty string
 */
import { formatDate, formatTimeOnly } from '@/composables/dateUtils'

export function extractHuntTargetDisplay(initialParameters, huntCategory) {
  if (!initialParameters || typeof initialParameters !== 'object') {
    return ''
  }

  // Define priority order for parameter extraction based on hunt category
  const parameterPriority = {
    domain: ['domain', 'hostname', 'url'],
    person: ['username', 'email', 'full_name', 'first_name', 'last_name'],
    company: ['company_name', 'organization', 'org_name', 'name'],
    ip: ['ip_address', 'ip', 'host'],
    phone: ['phone_number', 'phone'],
    email: ['email', 'email_address'],
    general: ['target', 'query', 'search_term'],
  }

  // Get parameter priority for this hunt category, fallback to general
  const priorities = parameterPriority[huntCategory] || parameterPriority.general

  // Try to find a parameter value in priority order
  for (const paramName of priorities) {
    if (paramName in initialParameters) {
      const value = initialParameters[paramName]
      if (value && typeof value === 'string' && value.trim()) {
        return value.trim()
      }
    }
  }

  // If no priority parameters found, try to find any meaningful string parameter
  const fallbackParams = ['domain', 'username', 'email', 'target', 'query', 'search', 'name']
  for (const paramName of fallbackParams) {
    if (paramName in initialParameters) {
      const value = initialParameters[paramName]
      if (value && typeof value === 'string' && value.trim()) {
        return value.trim()
      }
    }
  }

  // If still no value found, try the first string parameter
  const allParams = Object.keys(initialParameters)
  for (const paramName of allParams) {
    const value = initialParameters[paramName]
    if (value && typeof value === 'string' && value.trim() && paramName !== 'save_to_case') {
      return value.trim()
    }
  }

  return ''
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
    cancelled: 'grey',
    skipped: 'warning'
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
    cancelled: 'mdi-stop',
    skipped: 'mdi-skip-next'
  }
  return statusIcons[status] || 'mdi-help'
}

// Status text mapping
export const getStatusText = (status) => {
  const statusTexts = {
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    partial: 'Partial Success',
    failed: 'Failed',
    cancelled: 'Cancelled',
    skipped: 'Skipped'
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
    general: 'mdi-magnify'
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
    general: 'secondary'
  }
  return colorMap[category] || colorMap.general
}

// Format date/time
export const formatDateTime = (dateString) => {
  return formatDate(dateString) || 'N/A'
}

// Format time only
export const formatTime = (timestamp) => {
  return formatTimeOnly(timestamp)
}

// Calculate and format duration
export const calculateDuration = (startTime, endTime) => {
  if (!startTime) return 'N/A'
  
  const start = new Date(startTime)
  const end = endTime ? new Date(endTime) : new Date()
  const diffMs = end - start
  
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
  return paramName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Format metadata values
export const formatMetadataValue = (value) => {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

// Get log entry CSS class
export const getLogEntryClass = (type) => {
  const classMap = {
    error: 'log-error',
    warning: 'log-warning',
    info: 'log-info'
  }
  return classMap[type] || 'log-default'
}

// Export results to JSON
export const exportToJSON = (data, filename) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}
