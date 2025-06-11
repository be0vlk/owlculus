import { reactive, watch } from 'vue'
import { entityService } from '../services/entity'
import { cleanFormData } from '../utils/cleanFormData'

export function useEntityForm(caseId) {
  const state = reactive({
    entityType: 'person',
    data: {
      social_media: {
        x: '',
        linkedin: '',
        facebook: '',
        instagram: '',
        tiktok: '',
        reddit: '',
        other: '',
      },
      ip_addresses: [],
      subdomains: [],
      sources: {},
    },
    loading: false,
    error: null,
  })

  const resetFormData = (entityType) => {
    const baseSocialMedia = state.data.social_media
    state.data = {
      social_media: baseSocialMedia,
      ip_addresses: [],
      subdomains: [],
      sources: {},
    }

    switch (entityType) {
      case 'person':
        Object.assign(state.data, {
          first_name: '',
          last_name: '',
        })
        break
      case 'company':
        Object.assign(state.data, {
          name: '',
        })
        break
      case 'domain':
        Object.assign(state.data, {
          domain: '',
          description: '',
        })
        break
      case 'ip_address':
        Object.assign(state.data, {
          ip_address: '',
          description: '',
        })
        break
    }
  }

  const setEntityType = (type) => {
    state.entityType = type
    resetFormData(type)
  }

  const updateData = (data) => {
    state.data = { ...state.data, ...data }
  }

  const submitEntity = async () => {
    state.loading = true
    state.error = null

    try {
      const submitData = {
        entity_type: state.entityType,
        data: cleanFormData({ ...state.data }),
      }

      const response = await entityService.createEntity(caseId, submitData)
      return response
    } catch (error) {
      state.error = error.message || 'Failed to create entity'
      throw error
    } finally {
      state.loading = false
    }
  }

  const reset = () => {
    state.entityType = 'person'
    resetFormData('person')
    state.error = null
  }

  // Watch for entity type changes
  watch(
    () => state.entityType,
    (newType) => {
      resetFormData(newType)
    },
  )

  return {
    state,
    setEntityType,
    updateData,
    submitEntity,
    reset,
  }
}
