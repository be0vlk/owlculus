import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { caseService } from '../services/case'
import { clientService } from '../services/client'
import { formatDate } from '@/composables/dateUtils'

export const columns = [
  { key: 'case_number', label: 'Case Number' },
  { key: 'title', label: 'Title' },
  { key: 'client_name', label: 'Client' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Created' },
  { key: 'users', label: 'Assigned To' }
]

export function useDashboard () {
  const router = useRouter()
  const authStore = useAuthStore()

  const cases = ref([])
  const clients = ref({})
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
      // Load cases with status filter
      const params = {}
      if (!showClosedCases.value) {
        params.status = 'Open'
      }
      const casesData = await caseService.getCases(params)
      cases.value = casesData

      // Only try to load clients if user is admin
      if (authStore.requiresAdmin()) {
        try {
          const clientsData = await clientService.getClients()
          clients.value = clientsData.reduce((acc, client) => {
            acc[client.id] = client
            return acc
          }, {})
        } catch (err) {
          console.error('Failed to load clients:', err)
          // Don't set error state since this is expected for non-admin users
        }
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
    loadData()
  }

  // Watch for changes to showClosedCases and reload data
  watch(showClosedCases, () => {
    loadData()
  })

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
    return assignedUsers.map(user => user.username).join(', ')
  }

  const sortedAndFilteredCases = computed(() => {
    let filteredCases = cases.value

    // Apply search filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      filteredCases = filteredCases.filter(case_ => {
        // Search in basic case fields
        const basicFieldsMatch =
          (case_.case_number || '').toLowerCase().includes(query) ||
          (case_.title || '').toLowerCase().includes(query) ||
          (getClientName(case_.client_id) || '').toLowerCase().includes(query) ||
          (case_.status || '').toLowerCase().includes(query)

        // Search in assigned user names
        const assignedUsersMatch = case_.users?.some(user =>
          (user.username || '').toLowerCase().includes(query)
        ) || false

        return basicFieldsMatch || assignedUsersMatch
      })
    }

    // Apply sorting
    return [...filteredCases].sort((a, b) => {
      let aValue = sortKey.value === 'client_name'
        ? getClientName(a.client_id)
        : a[sortKey.value]
      let bValue = sortKey.value === 'client_name'
        ? getClientName(b.client_id)
        : b[sortKey.value]

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
    sortedAndFilteredCases
  }
}
