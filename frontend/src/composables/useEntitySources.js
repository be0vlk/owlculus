export function useEntitySources(entity, formData, isEditing) {
  function getSourceValue(parentField, fieldId) {
    const sources = isEditing.value ? formData.value.data.sources : entity.value.data.sources
    if (!sources) return ''

    const sourceKey = parentField ? `${parentField}.${fieldId}` : fieldId
    return sources[sourceKey] || ''
  }

  function updateSourceValue(parentField, fieldId, value) {
    if (!formData.value.data.sources) {
      formData.value.data.sources = {}
    }

    const sourceKey = parentField ? `${parentField}.${fieldId}` : fieldId
    if (value) {
      formData.value.data.sources[sourceKey] = value
    } else {
      delete formData.value.data.sources[sourceKey]
    }
  }

  return {
    getSourceValue,
    updateSourceValue,
  }
}
