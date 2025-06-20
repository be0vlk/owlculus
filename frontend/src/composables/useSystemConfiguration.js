import { ref, computed } from 'vue'
import api from '@/services/api'

export function useSystemConfiguration () {
  // State
  const selectedTemplate = ref('YYMM-NN')
  const caseNumberPrefix = ref('')
  const originalTemplate = ref('YYMM-NN')
  const originalPrefix = ref('')
  const configLoading = ref(false)
  const exampleCaseNumber = ref('')

  // Configuration options
  const templateOptions = [
    { display_name: 'Monthly Reset (YYMM-NN)', value: 'YYMM-NN' },
    { display_name: 'Prefix + Monthly Reset (PREFIX-YYMM-NN)', value: 'PREFIX-YYMM-NN' }
  ]

  // Computed properties
  const isConfigChanged = computed(() => {
    return (
      selectedTemplate.value !== originalTemplate.value ||
      caseNumberPrefix.value !== originalPrefix.value
    )
  })

  const isConfigValid = computed(() => {
    if (selectedTemplate.value === 'PREFIX-YYMM-NN') {
      return validatePrefix(caseNumberPrefix.value) === true
    }
    return true
  })

  // Validation functions
  const validatePrefix = (value) => {
    if (selectedTemplate.value === 'PREFIX-YYMM-NN') {
      if (!value) return 'Prefix is required'
      if (!/^[A-Za-z0-9]{2,8}$/.test(value)) {
        return 'Prefix must be 2-8 alphanumeric characters'
      }
    }
    return true
  }

  // Configuration methods
  const updatePreview = async () => {
    if (!isConfigValid.value) {
      exampleCaseNumber.value = ''
      return
    }

    try {
      const params = new URLSearchParams({
        template: selectedTemplate.value
      })

      if (selectedTemplate.value === 'PREFIX-YYMM-NN' && caseNumberPrefix.value) {
        params.append('prefix', caseNumberPrefix.value)
      }

      const response = await api.get(`/api/admin/configuration/preview?${params}`)
      exampleCaseNumber.value = response.data.example_case_number
    } catch (error) {
      console.error('Error updating preview:', error)
      exampleCaseNumber.value = ''
    }
  }

  const onTemplateChange = async () => {
    if (selectedTemplate.value !== 'PREFIX-YYMM-NN') {
      caseNumberPrefix.value = ''
    }
    await updatePreview()
  }

  const onPrefixChange = async () => {
    await updatePreview()
  }

  const loadConfiguration = async () => {
    try {
      const response = await api.get('/api/admin/configuration')
      const config = response.data

      selectedTemplate.value = config.case_number_template
      caseNumberPrefix.value = config.case_number_prefix || ''
      originalTemplate.value = config.case_number_template
      originalPrefix.value = config.case_number_prefix || ''

      await updatePreview()
    } catch (error) {
      console.error('Error loading configuration:', error)
      throw error
    }
  }

  const saveConfiguration = async () => {
    if (!isConfigValid.value) return

    configLoading.value = true
    try {
      const configData = {
        case_number_template: selectedTemplate.value,
        case_number_prefix:
          selectedTemplate.value === 'PREFIX-YYMM-NN' ? caseNumberPrefix.value : null
      }

      await api.put('/api/admin/configuration', configData)

      originalTemplate.value = selectedTemplate.value
      originalPrefix.value = caseNumberPrefix.value

      return true
    } catch (error) {
      console.error('Error saving configuration:', error)
      throw error
    } finally {
      configLoading.value = false
    }
  }

  const resetConfiguration = () => {
    selectedTemplate.value = originalTemplate.value
    caseNumberPrefix.value = originalPrefix.value
    updatePreview()
  }

  return {
    // State
    selectedTemplate,
    caseNumberPrefix,
    originalTemplate,
    originalPrefix,
    configLoading,
    exampleCaseNumber,

    // Constants
    templateOptions,

    // Computed
    isConfigChanged,
    isConfigValid,

    // Validation
    validatePrefix,

    // Methods
    updatePreview,
    onTemplateChange,
    onPrefixChange,
    loadConfiguration,
    saveConfiguration,
    resetConfiguration
  }
}
