import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useActiveCaseStore } from '../stores/activeCase'
import { useClientsStore } from '../stores/clients'
import { formatDate } from '@/composables/dateUtils'

export const columns = [
  { key: 'case_number', label: 'Case Number' },
  { key: 'title', label: 'Title' },
  { key: 'client_name', label: 'Client' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Created' },
  { key: 'users', label: 'Assigned To' },
]

export function useDashboard() {
  const router = useRouter()
  const authStore = useAuthStore()

  const activeCase = useActiveCaseStore()
  const cases = computed(() => activeCase.accessibleCases)
  const clientsStore = useClientsStore()
  const clients = computed(() =>
    Object.fromEntries(clientsStore.clients.map((client) => [client.id, client])),
  )
  const loading = ref(true)
  const error = ref(null)
  const searchQuery = ref('')
  const sortKey = ref('created_at')
  const sortOrder = ref('desc')
  const showClosedCases = ref(false)

  const loadData = async () => {
    if (!authStore.isAuthenticated) {
      router.push('/login')
      return
    }

    try {
      loading.value = true
      error.value = null
      await activeCase.refresh()
      if (activeCase.error) throw new Error(activeCase.error)

      // Load clients for all authenticated users since read ops are not sensitive
      try {
        await clientsStore.refresh()
      } catch (err) {
        console.error('Failed to load clients:', err)
        // Don't set error state for client loading failures
      }

      loading.value = false
    } catch (err) {
      error.value = 'Failed to load dashboard data'
      loading.value = false
      console.error('Dashboard loading error:', err)
    }
  }

  const toggleClosedCases = () => {
    showClosedCases.value = !showClosedCases.value
  }

  const sortBy = (key) => {
    if (sortKey.value === key) {
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey.value = key
      sortOrder.value = 'asc'
    }
  }

  const getClientName = (clientId) => {
    return clients.value[clientId]?.name || 'Unknown Client'
  }

  const getAssignedUsers = (assignedUsers) => {
    if (!assignedUsers || assignedUsers.length === 0) return 'Unassigned'
    return assignedUsers.map((user) => user.username).join(', ')
  }

  const sortedAndFilteredCases = computed(() => {
    let filteredCases = showClosedCases.value
      ? cases.value
      : cases.value.filter((item) => item.status === 'Open')

    // Apply search filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      filteredCases = filteredCases.filter((case_) => {
        // Search in basic case fields
        const basicFieldsMatch =
          (case_.case_number || '').toLowerCase().includes(query) ||
          (case_.title || '').toLowerCase().includes(query) ||
          (getClientName(case_.client_id) || '').toLowerCase().includes(query) ||
          (case_.status || '').toLowerCase().includes(query)

        // Search in assigned user names
        const assignedUsersMatch =
          case_.users?.some((user) => (user.username || '').toLowerCase().includes(query)) || false

        return basicFieldsMatch || assignedUsersMatch
      })
    }

    // Apply sorting
    return [...filteredCases].sort((a, b) => {
      let aValue = sortKey.value === 'client_name' ? getClientName(a.client_id) : a[sortKey.value]
      let bValue = sortKey.value === 'client_name' ? getClientName(b.client_id) : b[sortKey.value]

      if (typeof aValue === 'string') aValue = aValue.toLowerCase()
      if (typeof bValue === 'string') bValue = bValue.toLowerCase()

      if (aValue < bValue) return sortOrder.value === 'asc' ? -1 : 1
      if (aValue > bValue) return sortOrder.value === 'asc' ? 1 : -1
      return 0
    })
  })

  return {
    // State
    cases,
    loading,
    error,
    searchQuery,
    sortKey,
    sortOrder,
    showClosedCases,

    // Methods
    loadData,
    sortBy,
    getClientName,
    formatDate,
    getAssignedUsers,
    toggleClosedCases,

    // Computed
    sortedAndFilteredCases,
  }
}
