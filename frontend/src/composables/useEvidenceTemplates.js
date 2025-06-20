import { ref } from 'vue'
import { systemService } from '@/services/system'
import { evidenceService } from '@/services/evidence'

export function useEvidenceTemplates () {
  const loading = ref(false)
  const error = ref('')
  const templates = ref({})

  const loadTemplates = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await systemService.getEvidenceFolderTemplates()
      templates.value = response.templates || {}
      return templates.value
    } catch (err) {
      error.value = 'Failed to load templates'
      console.error('Error loading templates:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const saveTemplates = async (updatedTemplates) => {
    loading.value = true
    error.value = ''
    try {
      await systemService.updateEvidenceFolderTemplates(updatedTemplates)
      templates.value = updatedTemplates
      return templates.value
    } catch (err) {
      error.value = 'Failed to save templates'
      console.error('Error saving templates:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const applyTemplate = async (caseId, templateName) => {
    loading.value = true
    error.value = ''
    try {
      const result = await evidenceService.applyFolderTemplate(caseId, templateName)
      return result
    } catch (err) {
      error.value = `Failed to apply template: ${templateName}`
      console.error('Error applying template:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const getTemplateOptions = () => {
    return Object.keys(templates.value).map((key) => ({
      value: key,
      text: templates.value[key].name,
      title: templates.value[key].name,
      description: templates.value[key].description
    }))
  }

  const getTemplate = (templateName) => {
    return templates.value[templateName] || null
  }

  const validateTemplate = (template) => {
    const errors = []

    if (!template.name || template.name.trim() === '') {
      errors.push('Template name is required')
    }

    if (!template.description || template.description.trim() === '') {
      errors.push('Template description is required')
    }

    if (!Array.isArray(template.folders)) {
      errors.push('Template must have a folders array')
    }

    return {
      isValid: errors.length === 0,
      errors
    }
  }

  const createDefaultTemplate = () => {
    return {
      name: 'New Template',
      description: 'Template description',
      folders: []
    }
  }

  const createDefaultFolder = () => {
    return {
      name: 'New Folder',
      description: '',
      subfolders: []
    }
  }

  return {
    // State
    loading,
    error,
    templates,

    // Methods
    loadTemplates,
    saveTemplates,
    applyTemplate,
    getTemplateOptions,
    getTemplate,
    validateTemplate,
    createDefaultTemplate,
    createDefaultFolder
  }
}
