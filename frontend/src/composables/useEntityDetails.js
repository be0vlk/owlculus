import { ref, computed, watch } from 'vue'
import { entityService } from '../services/entity'
import { entitySchemas } from './entitySchemas'
import { cleanFormData } from '../utils/cleanFormData'

export function useEntityDetails(entity, caseId) {
  const error = ref('')
  const isEditing = ref(false)
  const updating = ref(false)
  const activeTab = ref('basicInfo')

  const formData = ref({
    data: {
      address: {},
      social_media: {},
      aliases: [],
    },
  })

  const entitySchema = computed(() => {
    return entitySchemas[entity.value?.entity_type]
  })

  const flattenNestedFields = (data, schema) => {
    const result = { ...data }

    Object.entries(schema).forEach(([, section]) => {
      if (section.parentField && data[section.parentField]) {
        section.fields.forEach((field) => {
          const value = data[section.parentField][field.id]
          if (value !== undefined) {
            result[`${section.parentField}.${field.id}`] = value
          }
        })
      }
    })

    return result
  }

  const restructureNestedFields = (data, schema) => {
    const result = { ...data }

    Object.entries(schema).forEach(([, section]) => {
      if (section.parentField) {
        result[section.parentField] = result[section.parentField] || {}

        section.fields.forEach((field) => {
          const dotKey = `${section.parentField}.${field.id}`
          if (dotKey in result) {
            result[section.parentField][field.id] = result[dotKey]
            delete result[dotKey]
          }
        })
      }
    })

    return result
  }

  const startEditing = () => {
    const initialData = {
      ...entity.value.data,
      aliases: Array.isArray(entity.value.data.aliases) ? [...entity.value.data.aliases] : [],
      address: entity.value.data.address || {},
      social_media: entity.value.data.social_media || {},
      associates: entity.value.data.associates || {},
      executives: entity.value.data.executives || {},
      affiliates: entity.value.data.affiliates || {},
      notes: entity.value.data.notes || '',
    }

    const flattenedData = flattenNestedFields(initialData, entitySchema.value)

    formData.value = {
      data: flattenedData,
    }
    isEditing.value = true
  }

  const cancelEdit = () => {
    isEditing.value = false
    error.value = ''
  }

  const updateEntity = async (processAssociates) => {
    try {
      updating.value = true
      error.value = ''

      const cleanedData = cleanFormData({ ...formData.value.data })
      const restructuredData = restructureNestedFields(cleanedData, entitySchema.value)

      const submitData = {
        data: {
          ...restructuredData,
          aliases: Array.isArray(restructuredData.aliases) ? restructuredData.aliases : [],
          social_media: restructuredData.social_media || {},
          associates: restructuredData.associates || {},
          executives: restructuredData.executives || {},
          affiliates: restructuredData.affiliates || {},
          address: restructuredData.address || {},
          notes: restructuredData.notes || '',
        },
      }

      const updatedEntity = await entityService.updateEntity(caseId.value, entity.value.id, {
        entity_type: entity.value.entity_type,
        data: submitData.data,
      })

      let createdAssociates = []
      if (processAssociates) {
        createdAssociates = await processAssociates(submitData)
      }

      isEditing.value = false
      return { updatedEntity, createdAssociates }
    } catch (err) {
      error.value = err.response?.data?.message || err.message || 'Failed to update entity'
      throw err
    } finally {
      updating.value = false
    }
  }

  watch(
    () => entity.value,
    (newEntity, oldEntity) => {
      if (newEntity) {
        // Only update form data if we're not currently editing
        // or if it's a completely different entity
        if (!isEditing.value || !oldEntity || oldEntity.id !== newEntity.id) {
          const flattenedData = flattenNestedFields(
            {
              ...newEntity.data,
              aliases: Array.isArray(newEntity.data.aliases) ? [...newEntity.data.aliases] : [],
              address: newEntity.data.address || {},
              social_media: newEntity.data.social_media || {},
              associates: newEntity.data.associates || {},
              executives: newEntity.data.executives || {},
              affiliates: newEntity.data.affiliates || {},
              notes: newEntity.data.notes || '',
            },
            entitySchema.value,
          )

          formData.value = {
            data: flattenedData,
          }
        }

        // Only reset tab if this is a completely different entity (different ID)
        if (!oldEntity || oldEntity.id !== newEntity.id) {
          activeTab.value = Object.keys(entitySchema.value)[0]
        }
      }
    },
  )

  return {
    error,
    isEditing,
    updating,
    activeTab,
    formData,
    entitySchema,
    startEditing,
    cancelEdit,
    updateEntity,
  }
}
