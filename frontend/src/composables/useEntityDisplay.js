import { computed } from 'vue'
import { supportedProfile } from './useEntityValidation'

export function getEntityDisplayName(entity) {
  if (!entity) return ''
  const data = entity.data || {}
  const joined = (...fields) =>
    fields
      .map((field) => data[field] ?? '')
      .join(' ')
      .trim()
  switch (entity.entity_type) {
    case 'person':
      return (
        joined('first_name', 'last_name') ||
        data.email?.trim() ||
        data.phone?.trim() ||
        data.employer?.trim() ||
        [...Object.values(data.social_media || {}), ...(data.usernames || [])]
          .find(supportedProfile)
          ?.trim() ||
        `Person #${entity.id}`
      )
    case 'vehicle':
      return (
        joined('year', 'make', 'model') ||
        data.vin?.trim() ||
        data.license_plate?.trim() ||
        `Vehicle #${entity.id}`
      )
    case 'company':
      return data.name || 'Unnamed Company'
    case 'domain':
      return data.domain || 'Unnamed Domain'
    case 'ip_address':
      return data.ip_address || 'Unnamed IP'
    default:
      return 'Unnamed Entity'
  }
}

export function useEntityDisplay(entity) {
  const getEntityTitle = computed(() =>
    entity.value ? getEntityDisplayName(entity.value) : 'Entity Details',
  )
  const getFieldValue = (data, parentField, fieldId) =>
    parentField ? data[parentField]?.[fieldId] : data[fieldId]
  return { getEntityDisplayName, getEntityTitle, getFieldValue }
}
