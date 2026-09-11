import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { clientService } from '../services/client'
import { useAuthStore } from './auth'

export const useClientsStore = defineStore('clients', () => {
  const auth = useAuthStore()
  const clients = ref([])
  let generation = 0

  // Cached rows belong only to the current authenticated user and role.
  watch(
    () => [auth.isAuthenticated, auth.user?.id, auth.user?.role],
    () => {
      generation++
      clients.value = []
    },
    { flush: 'sync' },
  )

  async function refresh() {
    if (!auth.isAuthenticated) return
    const requestGeneration = ++generation
    try {
      const data = await clientService.getClients()
      if (requestGeneration === generation) clients.value = data
    } catch (error) {
      if (requestGeneration === generation && [401, 403].includes(error.response?.status)) {
        clients.value = []
      }
      throw error
    }
  }

  function upsert(client) {
    generation++
    clients.value = clients.value.some((item) => item.id === client.id)
      ? clients.value.map((item) => (item.id === client.id ? client : item))
      : [...clients.value, client]
  }

  function remove(id) {
    generation++
    clients.value = clients.value.filter((item) => item.id !== id)
  }

  return { clients, refresh, upsert, remove }
})
