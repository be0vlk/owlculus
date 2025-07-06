import { ref, computed } from 'vue'
import { taskService } from '@/services/task'

export function useTaskTemplates() {
  // State
  const loading = ref(false)
  const saving = ref(false)
  const deleting = ref(false)
  const error = ref('')
  const templates = ref([])
  const showAddDialog = ref(false)
  const showEditDialog = ref(false)
  const editingTemplate = ref(null)

  // Form state
  const newTemplateForm = ref({
    name: '',
    display_name: '',
    description: '',
    category: '',
    is_active: true,
    definition_json: {
      fields: [],
    },
  })

  const editTemplateForm = ref({
    name: '',
    display_name: '',
    description: '',
    category: '',
    is_active: true,
    definition_json: {
      fields: [],
    },
  })

  // Computed
  const sortedTemplates = computed(() => {
    return [...templates.value].sort((a, b) => {
      // Sort by category first, then by display name
      if (a.category !== b.category) {
        return a.category.localeCompare(b.category)
      }
      return a.display_name.localeCompare(b.display_name)
    })
  })

  const isFormValid = computed(() => {
    const form = showAddDialog.value ? newTemplateForm.value : editTemplateForm.value
    return !!(
      form.name &&
      form.display_name &&
      form.description &&
      form.category &&
      validateTemplateName(form.name) === true
    )
  })

  // Validation functions
  const validateTemplateName = (value) => {
    if (!value) return 'Template name is required'
    if (!/^[a-z0-9_-]+$/.test(value)) {
      return 'Template name must contain only lowercase letters, numbers, underscores, and hyphens'
    }
    // Check for uniqueness when adding new template
    if (showAddDialog.value && templates.value.some((t) => t.name === value)) {
      return 'Template name already exists'
    }
    return true
  }

  const validateDisplayName = (value) => {
    if (!value) return 'Display name is required'
    if (value.length < 3) return 'Display name must be at least 3 characters'
    return true
  }

  const validateDescription = (value) => {
    if (!value) return 'Description is required'
    return true
  }

  const validateCategory = (value) => {
    if (!value) return 'Category is required'
    return true
  }

  // Methods
  const loadTemplates = async () => {
    loading.value = true
    error.value = ''
    try {
      templates.value = await taskService.getTemplates(true) // Include inactive
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to load templates'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createTemplate = async () => {
    saving.value = true
    error.value = ''
    try {
      const newTemplate = await taskService.createCustomTemplate(newTemplateForm.value)
      templates.value.push(newTemplate)
      closeAddDialog()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to create template'
      throw err
    } finally {
      saving.value = false
    }
  }

  const updateTemplate = async () => {
    saving.value = true
    error.value = ''
    try {
      // Note: We'll need to add an update endpoint to the backend
      const response = await taskService.updateTemplate(
        editingTemplate.value.id,
        editTemplateForm.value,
      )
      const index = templates.value.findIndex((t) => t.id === editingTemplate.value.id)
      if (index !== -1) {
        templates.value[index] = response
      }
      closeEditDialog()
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to update template'
      throw err
    } finally {
      saving.value = false
    }
  }

  const deleteTemplate = async (templateId) => {
    deleting.value = true
    error.value = ''
    try {
      // Note: We'll need to add a delete endpoint to the backend
      await taskService.deleteTemplate(templateId)
      templates.value = templates.value.filter((t) => t.id !== templateId)
    } catch (err) {
      error.value = err.response?.data?.detail || 'Failed to delete template'
      throw err
    } finally {
      deleting.value = false
    }
  }

  const openAddDialog = () => {
    newTemplateForm.value = {
      name: '',
      display_name: '',
      description: '',
      category: '',
      is_active: true,
      definition_json: {
        fields: [],
      },
    }
    showAddDialog.value = true
  }

  const openEditDialog = (template) => {
    editingTemplate.value = template
    editTemplateForm.value = {
      name: template.name,
      display_name: template.display_name,
      description: template.description,
      category: template.category,
      is_active: template.is_active,
      definition_json: JSON.parse(JSON.stringify(template.definition_json || { fields: [] })),
    }
    showEditDialog.value = true
  }

  const closeAddDialog = () => {
    showAddDialog.value = false
    newTemplateForm.value = {
      name: '',
      display_name: '',
      description: '',
      category: '',
      is_active: true,
      definition_json: {
        fields: [],
      },
    }
  }

  const closeEditDialog = () => {
    showEditDialog.value = false
    editingTemplate.value = null
  }

  // Field management for definition_json
  const addField = (form) => {
    if (!form.definition_json.fields) {
      form.definition_json.fields = []
    }
    form.definition_json.fields.push({
      name: '',
      type: 'string',
      required: false,
      label: '',
      description: '',
    })
  }

  const removeField = (form, index) => {
    form.definition_json.fields.splice(index, 1)
  }

  const validateField = (field) => {
    const errors = []
    if (!field.name) errors.push('Field name is required')
    if (!/^[a-zA-Z0-9_]+$/.test(field.name))
      errors.push('Field name must be alphanumeric with underscores')
    if (!field.label) errors.push('Field label is required')
    return errors
  }

  return {
    // State
    loading,
    saving,
    deleting,
    error,
    templates,
    showAddDialog,
    showEditDialog,
    editingTemplate,
    newTemplateForm,
    editTemplateForm,

    // Computed
    sortedTemplates,
    isFormValid,

    // Validation
    validateTemplateName,
    validateDisplayName,
    validateDescription,
    validateCategory,
    validateField,

    // Methods
    loadTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    openAddDialog,
    openEditDialog,
    closeAddDialog,
    closeEditDialog,
    addField,
    removeField,
  }
}
