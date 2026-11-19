import { useEntityAdvisories } from './useEntityAdvisories'
import { reactive, watch } from 'vue'
import { entityService } from '../services/entity'
import { cleanFormData } from '../utils/cleanFormData'
import { getErrorMessage } from '../utils/errorMessage'

export function useEntityForm(caseId) {
  const advisories = useEntityAdvisories(caseId)
  const state = reactive({ entityType: 'person', data: {}, loading: false, error: null })

  const submitEntity = async (confirmed = false) => {
    state.loading = true
    state.error = null

    try {
      const submitData = {
        entity_type: state.entityType,
        data: cleanFormData({ ...state.data }),
      }

      if (!(await advisories.check(submitData, confirmed))) return null
      const response = await entityService.createEntity(caseId, submitData)
      return response
    } catch (error) {
      state.error = getErrorMessage(error, 'Failed to create entity')
      throw error
    } finally {
      state.loading = false
    }
  }

  const reset = () => {
    advisories.clear()
    state.entityType = 'person'
    state.data = {}
    state.error = null
  }

  watch(
    () => state.entityType,
    () => {
      advisories.clear()
      state.data = {}
    },
  )

  return { state, advisories, submitEntity, reset }
}

export const entityFormProps = {
  modelValue: {
    type: Object,
    required: true,
  },
}

export const entityFormEmits = ['update:modelValue']

export function useEntityFormField(props, emit) {
  const updateField = (field, value) => {
    emit('update:modelValue', {
      ...props.modelValue,
      [field]: value,
    })
  }

  return {
    updateField,
  }
}
