import { ref, watch } from 'vue'
import { entityService } from '../services/entity'

export function useEntityAssociates(entity, existingEntities, caseId) {
  const associateEntityMap = ref(new Map())

  const getAssociateEntities = (fieldId) => {
    return associateEntityMap.value.get(fieldId) || []
  }

  const findExistingCompany = (companyName) => {
    return existingEntities.value.find(
      (entity) =>
        entity.entity_type === 'company' &&
        entity.data.name?.toLowerCase() === companyName.toLowerCase(),
    )
  }

  const createOrUpdateCompanyEntity = async (companyName) => {
    let companyEntity = findExistingCompany(companyName)

    if (!companyEntity) {
      companyEntity = await entityService.createEntity(caseId.value, {
        entity_type: 'company',
        data: {
          name: companyName,
        },
      })
    }

    return companyEntity
  }

  const processAssociates = async (submitData) => {
    if (!entity.value || entity.value.entity_type !== 'person') {
      return []
    }

    const createdAssociates = []
    associateEntityMap.value.clear()

    // Handle employer field to create company entities
    const employerName = submitData.data.employer
    if (employerName && employerName.trim()) {
      try {
        const companyEntity = await createOrUpdateCompanyEntity(employerName.trim())
        createdAssociates.push(companyEntity)
        associateEntityMap.value.set('employer', [companyEntity])
      } catch (err) {
        console.error(`Failed to handle employer entity for ${employerName}:`, err)
      }
    }

    return createdAssociates
  }

  const loadAssociateEntities = async () => {
    if (!entity.value?.entity_type === 'person') {
      return
    }

    associateEntityMap.value.clear()

    // Load employer entity if it exists
    const employerName = entity.value.data.employer
    if (employerName && employerName.trim()) {
      try {
        let companyEntity = findExistingCompany(employerName.trim())

        if (!companyEntity) {
          // Create a temporary entity for display purposes
          companyEntity = {
            id: `temp_employer_${employerName}`,
            entity_type: 'company',
            data: {
              name: employerName.trim(),
            },
          }
        }

        associateEntityMap.value.set('employer', [companyEntity])
      } catch (err) {
        console.error(`Failed to load employer entity for ${employerName}:`, err)
      }
    }
  }

  watch(() => entity.value, loadAssociateEntities, { immediate: true })

  return {
    associateEntityMap,
    getAssociateEntities,
    processAssociates,
    loadAssociateEntities,
  }
}
