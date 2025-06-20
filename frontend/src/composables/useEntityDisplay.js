import { computed } from 'vue'

export function useEntityDisplay (entity) {
  const getEntityDisplayName = (targetEntity) => {
    if (targetEntity.entity_type === 'person') {
      return `${targetEntity.data.first_name} ${targetEntity.data.last_name}`.trim()
    }
    return targetEntity.data.name || 'Unnamed Entity'
  }

  const getEntityTitle = computed(() => {
    if (!entity.value) return 'Entity Details'

    if (entity.value.entity_type === 'person') {
      return `${entity.value.data.first_name} ${entity.value.data.last_name}`
    }
    return entity.value.data.name || 'Entity Details'
  })

  const getFieldValue = (data, parentField, fieldId) => {
    if (parentField) {
      return data[parentField]?.[fieldId]
    }
    return data[fieldId]
  }

  return {
    getEntityDisplayName,
    getEntityTitle,
    getFieldValue
  }
}
