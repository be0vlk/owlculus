import { ref } from 'vue'

export function useDashboardLayout() {
  const loading = ref(false)
  const error = ref(null)
  const searchQuery = ref('')
  const sortKey = ref('')
  const sortOrder = ref('desc')

  const clearError = () => {
    error.value = null
  }

  const setLoading = (state) => {
    loading.value = state
    if (state) {
      error.value = null
    }
  }

  const setError = (message) => {
    error.value = message
    loading.value = false
  }

  const createCardHeader = (icon, title, subtitle) => ({
    icon,
    title,
    subtitle,
  })

  const sortBy = (key) => {
    if (sortKey.value === key) {
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey.value = key
      sortOrder.value = 'asc'
    }
  }

  const applySorting = (items, getValue = null) => {
    if (!sortKey.value) return items

    return [...items].sort((a, b) => {
      let aValue = getValue ? getValue(a, sortKey.value) : a[sortKey.value]
      let bValue = getValue ? getValue(b, sortKey.value) : b[sortKey.value]

      if (typeof aValue === 'string') aValue = aValue.toLowerCase()
      if (typeof bValue === 'string') bValue = bValue.toLowerCase()

      if (aValue < bValue) return sortOrder.value === 'asc' ? -1 : 1
      if (aValue > bValue) return sortOrder.value === 'asc' ? 1 : -1
      return 0
    })
  }

  const applySearch = (items, searchFields) => {
    if (!searchQuery.value) return items

    const query = searchQuery.value.toLowerCase()
    return items.filter((item) => {
      return searchFields.some((field) => {
        const value = typeof field === 'function' ? field(item) : item[field]
        return value && value.toString().toLowerCase().includes(query)
      })
    })
  }

  const processItems = (items, searchFields, getValue = null) => {
    let processed = applySearch(items, searchFields)
    processed = applySorting(processed, getValue)
    return processed
  }

  return {
    loading,
    error,
    searchQuery,
    sortKey,
    sortOrder,
    clearError,
    setLoading,
    setError,
    createCardHeader,
    sortBy,
    applySorting,
    applySearch,
    processItems,
  }
}
