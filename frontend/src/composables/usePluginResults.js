import { computed } from 'vue'
import { formatDate } from '@/composables/dateUtils'

export function usePluginResults(result) {
  const byType = (type) => computed(() => result.value.filter((item) => item.type === type))

  return {
    statusMessages: byType('status'),
    completionMessages: byType('complete'),
    errorMessages: byType('error'),
    dataResults: byType('data'),
  }
}

// Plugin output dates may be free text ("Unknown", registrar formats); show those as-is.
export const formatResultDate = (value) =>
  Number.isNaN(Date.parse(value)) ? value || 'Unknown' : formatDate(value)
