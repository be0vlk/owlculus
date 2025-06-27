/**
 * Hunt display utilities for extracting meaningful information from hunt executions
 */

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

  // Define priority order for parameter extraction based on hunt category
  const parameterPriority = {
    domain: ['domain', 'hostname', 'url'],
    person: ['username', 'email', 'full_name', 'first_name', 'last_name'],
    company: ['company_name', 'organization', 'org_name', 'name'],
    ip: ['ip_address', 'ip', 'host'],
    phone: ['phone_number', 'phone'],
    email: ['email', 'email_address'],
    general: ['target', 'query', 'search_term']
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