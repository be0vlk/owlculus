import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { caseService } from '../services/case'
import { caseLocation, routeCaseId } from '../utils/caseNavigation'

export const ACTIVE_CASE_STORAGE_KEY = 'owlculus.active-case'

function readPreference() {
  try {
    return localStorage.getItem(ACTIVE_CASE_STORAGE_KEY)
  } catch {
    return null
  }
}

export const useActiveCaseStore = defineStore('activeCase', () => {
  let generation = 0
  let pending
  let router

  function bindRouter(appRouter) {
    router = appRouter
  }
  const accessibleCases = ref([])
  const selectedId = ref(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const initialized = ref(false)
  const error = ref(null)
  const notification = ref('')
  const activeCase = computed(
    () => accessibleCases.value.find((item) => item.id === selectedId.value) || null,
  )
  const ready = computed(() => initialized.value && !loading.value && !error.value)
  const activeCaseId = computed(() => (ready.value ? (activeCase.value?.id ?? null) : null))

  function findCase(id) {
    return accessibleCases.value.find((item) => String(item.id) === String(id))
  }

  function persist(id) {
    selectedId.value = id
    try {
      if (id == null) localStorage.removeItem(ACTIVE_CASE_STORAGE_KEY)
      else localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, String(id))
    } catch {
      // Storage is a best-effort preference; authorized in-memory context still works.
    }
  }

  function newestCase() {
    return [...accessibleCases.value].sort((a, b) => {
      const byDate = (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0)
      return byDate || a.id - b.id
    })[0]
  }

  function resolve(urlCaseId) {
    const preferredId = urlCaseId ?? selectedId.value ?? readPreference()
    const preferred = findCase(preferredId)
    if (preferredId != null && !preferred) {
      notification.value =
        'The selected case is unavailable. ' +
        (accessibleCases.value.length
          ? 'Switched to the newest accessible case.'
          : 'No accessible cases remain.')
    }
    persist((preferred || newestCase())?.id ?? null)
  }

  function reset() {
    generation++
    pending = null
    accessibleCases.value = []
    selectedId.value = null
    initialized.value = false
    loading.value = false
    refreshing.value = false
    error.value = null
    notification.value = ''
  }

  function initialize(urlCaseId, unavailableId) {
    const request = loadCases(urlCaseId, unavailableId)
    pending = request
    return request.finally(() => {
      if (pending === request) pending = null
    })
  }

  async function waitForResolution() {
    while (pending) await pending
  }

  async function loadCases(urlCaseId, unavailableId) {
    const requestGeneration = ++generation
    // Revalidate an already authorized workspace without discarding its dialogs.
    // Known access failures require a blocking resolution immediately.
    refreshing.value = initialized.value && unavailableId == null
    loading.value = !refreshing.value
    try {
      const cases = []
      const pageSize = 100
      for (let skip = 0; ; skip += pageSize) {
        const page = await caseService.getCases({ skip, limit: pageSize })
        if (requestGeneration !== generation) return
        cases.push(...page)
        if (page.length < pageSize) break
      }
      accessibleCases.value = cases.filter((item) => String(item.id) !== String(unavailableId))
      resolve(urlCaseId)
      initialized.value = true
      error.value = null
    } catch {
      if (requestGeneration !== generation) return
      error.value = 'Unable to load accessible cases. Please retry.'
    } finally {
      if (requestGeneration === generation) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  async function refresh({ unavailableId } = {}) {
    const hadActiveCase = selectedId.value != null
    await initialize(routeCaseId(router?.currentRoute.value), unavailableId)
    if (!ready.value || !router) return
    const route = router.currentRoute.value
    if (hadActiveCase && !activeCaseId.value) {
      await router.replace('/cases')
      return
    }
    if (routeCaseId(route) && String(routeCaseId(route)) !== String(activeCaseId.value)) {
      await router.replace(caseLocation(activeCaseId.value, route))
    }
  }

  async function recoverUnavailable(id) {
    await refresh({ unavailableId: id })
  }

  async function select(id, options) {
    const selected = findCase(id)
    if (!ready.value || refreshing.value || !selected) return false
    persist(selected.id)
    if (router) await router.push(caseLocation(selected.id, router.currentRoute.value, options))
    return true
  }

  return {
    accessibleCases,
    activeCase,
    activeCaseId,
    loading,
    refreshing,
    initialized,
    ready,
    error,
    notification,
    initialize,
    reset,
    resolve,
    refresh,
    select,
    recoverUnavailable,
    bindRouter,
    waitForResolution,
  }
})
