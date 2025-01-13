<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <!-- Sidebar -->
      <Sidebar class="fixed inset-y-0 left-0" />

      <!-- Main content -->
      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="max-w-7xl mx-auto px-8 py-6">
            <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Clients Dashboard</h1>
          </div>
        </header>
        <main class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <!-- Loading state -->
          <div v-if="loading" class="flex justify-center items-center h-64">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 dark:border-cyan-400"></div>
          </div>

          <!-- Error state -->
          <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-400 dark:border-red-500 p-4 mb-4">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-red-400 dark:text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm text-red-700 dark:text-red-400">{{ error }}</p>
              </div>
            </div>
          </div>

          <!-- Clients table -->
          <div v-else class="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div class="px-6 py-5 border-b border-gray-200 dark:border-gray-700">
              <div class="flex items-center justify-between">
                <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100">All Clients</h2>
                <div class="flex items-center space-x-4">
                  <div class="relative w-96">
                    <input
                      type="text"
                      v-model="searchQuery"
                      placeholder="Search clients..."
                      class="w-full rounded-md border-0 py-2 pl-10 pr-3 text-gray-900 dark:text-gray-100 dark:bg-gray-700 ring-1 ring-inset ring-gray-300 dark:ring-gray-600 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:ring-2 focus:ring-cyan-600 text-sm"
                    />
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <svg class="h-5 w-5 text-gray-400 dark:text-gray-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
                      </svg>
                    </div>
                  </div>
                  <button
                    @click="openNewClientModal"
                    class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                  >
                    <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 01-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
                    </svg>
                    Add Client
                  </button>
                </div>
              </div>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead class="bg-gray-50 dark:bg-gray-700">
                  <tr>
                    <th 
                      v-for="column in columns" 
                      :key="column.key"
                      scope="col" 
                      class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:text-gray-700 dark:hover:text-gray-300 whitespace-nowrap"
                      @click="sortBy(column.key)"
                    >
                      <div class="flex items-center space-x-1">
                        <span>{{ column.label }}</span>
                        <span v-if="sortKey === column.key" class="ml-2">
                          {{ sortOrder === 'asc' ? '↑' : '↓' }}
                        </span>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  <tr v-for="client in sortedAndFilteredClients" :key="client.id" class="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td class="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                      {{ client.name }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">
                      {{ client.email }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                      {{ client.phone }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">
                      {{ client.address }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                      {{ formatDate(client.created_at) }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                      <button
                        @click="handleDelete(client)"
                        class="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                      >
                        <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
  </div>

  <!-- New Client Modal -->
  <NewClientModal
    :is-open="isNewClientModalOpen"
    @close="closeNewClientModal"
    @created="handleClientCreated"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import NewClientModal from '../components/NewClientModal.vue'
import { useClients } from '../composables/useClients'
import { clientService } from '../services/client'

const {
  loading,
  error,
  searchQuery,
  sortKey,
  sortOrder,
  clients,
  loadData,
  sortBy,
  formatDate,
  sortedAndFilteredClients,
  columns
} = useClients()

const isNewClientModalOpen = ref(false)

const openNewClientModal = () => {
  isNewClientModalOpen.value = true
}

const closeNewClientModal = () => {
  isNewClientModalOpen.value = false
}

const handleClientCreated = (newClient) => {
  clients.value.push(newClient)
}

const handleDelete = async (client) => {
  if (!confirm(`Are you sure you want to delete ${client.name}?`)) return

  try {
    await clientService.deleteClient(client.id)
    clients.value = clients.value.filter(c => c.id !== client.id)
  } catch (error) {
    console.error('Error deleting client:', error)
  }
}

onMounted(() => {
  loadData()
})
</script>
