import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { clientService } from '../services/client'
import { formatDate } from './dateUtils'

export const columns = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'address', label: 'Address' },
  { key: 'created_at', label: 'Created' }
]

export function useClients () {
  const router = useRouter()
  const authStore = useAuthStore()

  const clients = ref([])
  const loading = ref(true)
  const error = ref(null)
  const searchQuery = ref('')
  const sortKey = ref('name')
  const sortOrder = ref('asc')

  const loadData = async () => {
    if (!authStore.isAuthenticated) {
      router.push('/login')
      return
    }

    try {
      const clientsData = await clientService.getClients()
      clients.value = clientsData
    } catch (err) {
      error.value = 'Failed to load clients. Please try again later.'
      console.error('Error loading clients:', err)
    } finally {
      loading.value = false
    }
  }

  const sortBy = (key) => {
    if (sortKey.value === key) {
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey.value = key
      sortOrder.value = 'asc'
    }
  }

  const sortedAndFilteredClients = computed(() => {
    let filteredClients = clients.value

    // Apply search filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      filteredClients = filteredClients.filter(client =>
        (client.name || '').toLowerCase().includes(query) ||
        (client.email || '').toLowerCase().includes(query) ||
        (client.phone || '').toLowerCase().includes(query) ||
        (client.address || '').toLowerCase().includes(query)
      )
    }

    // Apply sorting
    return [...filteredClients].sort((a, b) => {
      const aVal = a[sortKey.value]
      const bVal = b[sortKey.value]

      if (aVal === bVal) return 0

      const comparison = aVal > bVal ? 1 : -1
      return sortOrder.value === 'asc' ? comparison : -comparison
    })
  })

  return {
    // State
    clients,
    loading,
    error,
    searchQuery,
    sortKey,
    sortOrder,

    // Methods
    loadData,
    sortBy,
    formatDate,

    // Computed
    sortedAndFilteredClients,

    // Constants
    columns
  }
}
