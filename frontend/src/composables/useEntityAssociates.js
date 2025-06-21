import { ref, watch } from 'vue'

export function useEntityAssociates (entity) {
  const associateEntityMap = ref(new Map())

  const getAssociateEntities = (fieldId) => {
    return associateEntityMap.value.get(fieldId) || []
  }


  const processAssociates = async () => {
    if (!entity.value || entity.value.entity_type !== 'person') {
      return []
    }

    const createdAssociates = []
    associateEntityMap.value.clear()

    // Removed automatic company entity creation for employer field
    // The employer field will now just be stored as text data

    return createdAssociates
  }

  const loadAssociateEntities = async () => {
    if (!entity.value?.entity_type === 'person') {
      return
    }

    associateEntityMap.value.clear()

    // Removed automatic loading of employer entities
    // The employer field is now just text data and doesn't create associated entities
  }

  watch(() => entity.value, loadAssociateEntities, { immediate: true })

  return {
    associateEntityMap,
    getAssociateEntities,
    processAssociates,
    loadAssociateEntities
  }
}
