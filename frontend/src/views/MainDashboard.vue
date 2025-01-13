<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <!-- Sidebar -->
      <Sidebar class="fixed inset-y-0 left-0" />

      <!-- Main content -->
      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="max-w-7xl mx-auto px-8 py-6">
            <div class="flex justify-between items-center">
              <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Case Dashboard</h1>
              <button
                v-if="authStore.requiresAdmin()"
                @click="isNewCaseModalOpen = true"
                class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 dark:bg-cyan-700 dark:hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 dark:focus:ring-offset-gray-900"
              >
                <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
                </svg>
                New Case
              </button>
            </div>
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

          <!-- Cases table -->
          <div v-else class="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div class="px-6 py-5 border-b border-gray-200 dark:border-gray-700">
              <div class="flex items-center justify-between">
                <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100">Cases</h2>
                <div class="flex items-center space-x-4">
                  <!-- Show Closed Cases Toggle -->
                  <div class="flex items-center">
                    <label for="showClosedCases" class="mr-3 text-sm font-medium text-gray-700 dark:text-gray-300">
                      Show Closed Cases
                    </label>
                    <button
                      type="button"
                      :class="[
                        showClosedCases ? 'bg-cyan-600' : 'bg-gray-200',
                        'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500'
                      ]"
                      role="switch"
                      :aria-checked="showClosedCases"
                      @click="toggleClosedCases"
                    >
                      <span
                        :class="[
                          showClosedCases ? 'translate-x-5' : 'translate-x-0',
                          'pointer-events-none relative inline-block h-5 w-5 transform rounded-full bg-white dark:bg-gray-200 shadow ring-0 transition duration-200 ease-in-out'
                        ]"
                      >
                        <span
                          :class="[
                            showClosedCases ? 'opacity-0 duration-100 ease-out' : 'opacity-100 duration-200 ease-in',
                            'absolute inset-0 flex h-full w-full items-center justify-center transition-opacity'
                          ]"
                          aria-hidden="true"
                        >
                          <svg class="h-3 w-3 text-gray-400" fill="none" viewBox="0 0 12 12">
                            <path
                              d="M4 8l2-2m0 0l2-2M6 6L4 4m2 2l2 2"
                              stroke="currentColor"
                              stroke-width="2"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                            />
                          </svg>
                        </span>
                        <span
                          :class="[
                            showClosedCases ? 'opacity-100 duration-200 ease-in' : 'opacity-0 duration-100 ease-out',
                            'absolute inset-0 flex h-full w-full items-center justify-center transition-opacity'
                          ]"
                          aria-hidden="true"
                        >
                          <svg class="h-3 w-3 text-cyan-600" fill="currentColor" viewBox="0 0 12 12">
                            <path d="M3.707 5.293a1 1 0 00-1.414 1.414l1.414-1.414zM5 8l-.707.707a1 1 0 001.414 0L5 8zm4.707-3.293a1 1 0 00-1.414-1.414l1.414 1.414zm-7.414 2l2 2 1.414-1.414-2-2-1.414 1.414zm3.414 2l4-4-1.414-1.414-4 4 1.414 1.414z" />
                          </svg>
                        </span>
                      </span>
                    </button>
                  </div>
                  <!-- Search Box -->
                  <div class="relative w-96">
                    <input
                      type="text"
                      v-model="searchQuery"
                      placeholder="Search cases..."
                      class="w-full rounded-md border-0 py-2 pl-10 pr-3 text-gray-900 dark:text-gray-100 dark:bg-gray-700 ring-1 ring-inset ring-gray-300 dark:ring-gray-600 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:ring-2 focus:ring-cyan-600 text-sm"
                    />
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <svg class="h-5 w-5 text-gray-400 dark:text-gray-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
                      </svg>
                    </div>
                  </div>
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
                      class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 whitespace-nowrap"
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
                  <tr 
                    v-for="case_ in sortedAndFilteredCases" 
                    :key="case_.id" 
                    class="hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                    @dblclick="router.push(`/case/${case_.id}`)"
                  >
                    <td class="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                      {{ case_.case_number }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">
                      {{ case_.title }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                      {{ getClientName(case_.client_id) }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                      <span :class="[
                        'px-3 py-1 text-sm font-medium rounded-full',
                        case_.status === 'Open' 
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' 
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                      ]">
                        {{ case_.status }}
                      </span>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                      {{ formatDate(case_.created_at) }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">
                      {{ case_.users?.map(user => user.username).join(', ') || 'Unassigned' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
    <NewCaseModal 
      :is-open="isNewCaseModalOpen" 
      @close="isNewCaseModalOpen = false" 
      @created="handleCaseCreated" 
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import NewCaseModal from '../components/NewCaseModal.vue'
import { useDashboard, columns } from '../composables/useDashboard'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const {
  loading,
  error,
  searchQuery,
  sortKey,
  sortOrder,
  showClosedCases,
  loadData,
  sortBy,
  getClientName,
  formatDate,
  getAssignedUsers,
  toggleClosedCases,
  sortedAndFilteredCases
} = useDashboard()

const isNewCaseModalOpen = ref(false)

const handleCaseCreated = (newCase) => {
  // Refresh the cases list
  loadData()
  isNewCaseModalOpen.value = false
}

onMounted(loadData)
</script>
