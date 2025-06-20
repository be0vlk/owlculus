import { computed } from 'vue'

export function usePluginResults (result) {
  const parsedResults = computed(() => {
    if (!result.value) return []

    if (Array.isArray(result.value)) {
      return result.value
    }

    if (result.value.type) {
      return [result.value]
    }

    return []
  })

  const legacyFormat = computed(() => {
    if (!result.value) return false
    return !Array.isArray(result.value) && !result.value.type
  })

  const statusMessages = computed(() =>
    parsedResults.value.filter((item) => item.type === 'status')
  )

  const completionMessages = computed(() =>
    parsedResults.value.filter((item) => item.type === 'complete')
  )

  const errorMessages = computed(() => parsedResults.value.filter((item) => item.type === 'error'))

  const dataResults = computed(() => parsedResults.value.filter((item) => item.type === 'data'))

  const hasResults = computed(() => parsedResults.value.length > 0 || legacyFormat.value)

  return {
    parsedResults,
    legacyFormat,
    statusMessages,
    completionMessages,
    errorMessages,
    dataResults,
    hasResults
  }
}
