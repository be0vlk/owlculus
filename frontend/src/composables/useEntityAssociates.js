import { ref, watch } from 'vue'
import { entityService } from '../services/entity'

export function useEntityAssociates(entity, existingEntities, caseId) {
  const associateEntityMap = ref(new Map())

  const getAssociateEntities = (fieldId) => {
    return associateEntityMap.value.get(fieldId) || []
  }

  const findExistingEntity = (firstName, lastName) => {
    const fullName = `${firstName} ${lastName}`.trim().toLowerCase()
    return existingEntities.value.find(
      (entity) =>
        entity.entity_type === 'person' &&
        `${entity.data.first_name} ${entity.data.last_name}`.trim().toLowerCase() === fullName,
    )
  }

  const createOrUpdateAssociateEntity = async (name, field, currentEntityName) => {
    const [firstName, ...lastNameParts] = name.split(' ')
    const lastName = lastNameParts.join(' ')

    let associateEntity = findExistingEntity(firstName, lastName)

    if (!associateEntity) {
      associateEntity = await entityService.createEntity(caseId.value, {
        entity_type: 'person',
        data: {
          first_name: firstName || name,
          last_name: lastName || '',
          associates: {
            [getReciprocalField(field)]: currentEntityName,
          },
        },
      })
    } else {
      const reciprocalField = getReciprocalField(field)
      const updatedAssociateData = {
        ...associateEntity.data,
        associates: {
          ...associateEntity.data.associates,
          [reciprocalField]: currentEntityName,
        },
      }

      associateEntity = await entityService.updateEntity(caseId.value, associateEntity.id, {
        entity_type: 'person',
        data: updatedAssociateData,
      })
    }

    return associateEntity
  }

  const getReciprocalField = (field) => {
    const reciprocalMap = {
      'partner/spouse': 'partner/spouse',
      father: 'children',
      mother: 'children',
      children: 'father',
      siblings: 'siblings',
      colleagues: 'colleagues',
      friends: 'friends',
    }
    return reciprocalMap[field] || 'other'
  }

  const processAssociates = async (submitData) => {
    if (!entity.value || entity.value.entity_type !== 'person' || !submitData.data.associates) {
      return []
    }

    const associateFields = [
      'children',
      'colleagues',
      'father',
      'friends',
      'mother',
      'partner/spouse',
      'siblings',
      'other',
    ]
    const createdAssociates = []
    associateEntityMap.value.clear()

    const currentEntityName = `${submitData.data.first_name} ${submitData.data.last_name}`.trim()

    for (const field of associateFields) {
      const associateNames = submitData.data.associates[field]
      if (associateNames) {
        const names = associateNames
          .split(',')
          .map((name) => name.trim())
          .filter((name) => name)
        const fieldAssociates = []

        for (const name of names) {
          try {
            const associateEntity = await createOrUpdateAssociateEntity(
              name,
              field,
              currentEntityName,
            )
            fieldAssociates.push(associateEntity)
            createdAssociates.push(associateEntity)
          } catch (err) {
            console.error(`Failed to handle associate entity for ${name}:`, err)
          }
        }

        if (fieldAssociates.length > 0) {
          associateEntityMap.value.set(field, fieldAssociates)
        }
      }
    }

    return createdAssociates
  }

  const loadAssociateEntities = async () => {
    if (!entity.value?.entity_type === 'person' || !entity.value.data.associates) {
      return
    }

    associateEntityMap.value.clear()
    const associateFields = [
      'children',
      'colleagues',
      'father',
      'friends',
      'mother',
      'partner/spouse',
      'siblings',
      'other',
    ]

    for (const field of associateFields) {
      const associateNames = entity.value.data.associates[field]
      if (associateNames) {
        try {
          const names = associateNames
            .split(',')
            .map((name) => name.trim())
            .filter((name) => name)
          const fieldAssociates = []

          for (const name of names) {
            const [firstName, ...lastNameParts] = name.split(' ')
            const lastName = lastNameParts.join(' ')

            let associateEntity = findExistingEntity(firstName, lastName)

            if (!associateEntity) {
              const existingEntity = {
                id: `temp_${field}_${name}`,
                entity_type: 'person',
                data: {
                  first_name: firstName || name,
                  last_name: lastName || '',
                },
              }
              fieldAssociates.push(existingEntity)
            } else {
              fieldAssociates.push(associateEntity)
            }
          }

          if (fieldAssociates.length > 0) {
            associateEntityMap.value.set(field, fieldAssociates)
          }
        } catch (err) {
          console.error(`Failed to load associate entities for ${field}:`, err)
        }
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
