import { ref } from 'vue'
import { entityService } from '@/services/entity'

export function useEntityAdvisories(caseId, excludeId) {
  const candidates = ref([])
  let reviewedPayload = ''
  const clear = () => {
    candidates.value = []
    reviewedPayload = ''
  }
  const check = async (payload, confirmed = false) => {
    const key = JSON.stringify(payload)
    if (confirmed && reviewedPayload === key && !candidates.value.some((item) => item.blocking)) {
      clear()
      return true
    }
    clear()
    if (!['person', 'vehicle'].includes(payload.entity_type)) return true
    candidates.value = await entityService.getDuplicateAdvisories(caseId, payload, excludeId)
    reviewedPayload = key
    return candidates.value.length === 0
  }
  return { candidates, check, clear }
}
