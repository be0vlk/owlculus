/**
 * Composable for standardized case selection functionality in plugin components
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { caseService } from '@/services/case'
import { formatDateOnly } from '@/composables/dateUtils'

export function useCaseSelection(props, emit) {
  // Local state
  const cases = ref([])
  const loadingCases = ref(true)

  // Local parameter state for save_to_case and case_id
  const caseParams = reactive({
    save_to_case:
      props.modelValue.save_to_case !== undefined ? props.modelValue.save_to_case : false,
    case_id: props.modelValue.case_id || null,
  })

  // Computed properties
  const caseItems = computed(() => {
    return cases.value.map((case_) => ({
      ...case_,
      display_name: `Case #${case_.case_number}: ${case_.title}`,
    }))
  })

  const selectedCase = computed(() => {
    if (!caseParams.case_id) return null
    return cases.value.find((case_) => case_.id === caseParams.case_id)
  })

  // Methods
  const loadCases = async () => {
    try {
      loadingCases.value = true
      const response = await caseService.getCases()
      cases.value = response
    } catch (error) {
      console.error('Failed to load cases:', error)
      cases.value = []
    } finally {
      loadingCases.value = false
    }
  }

  const updateCaseParams = () => {
    // If save_to_case is disabled, clear case_id
    if (!caseParams.save_to_case) {
      caseParams.case_id = null
    }

    // Emit both case selection parameters
    emit('update:modelValue', {
      ...props.modelValue,
      save_to_case: caseParams.save_to_case,
      case_id: caseParams.case_id,
    })
  }

  // Watch for external changes to modelValue
  watch(
    () => props.modelValue,
    (newValue) => {
      if (newValue.save_to_case !== undefined) {
        caseParams.save_to_case = newValue.save_to_case
      }
      if (newValue.case_id !== undefined) {
        caseParams.case_id = newValue.case_id
      }
    },
    { deep: true },
  )

  // Load cases on mount
  onMounted(() => {
    loadCases()
  })

  return {
    // State
    cases,
    loadingCases,
    caseParams,

    // Computed
    caseItems,
    selectedCase,

    // Methods
    loadCases,
    updateCaseParams,
    formatDateOnly,
  }
}
