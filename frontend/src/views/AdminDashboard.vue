<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <!-- Sidebar -->
      <Sidebar class="fixed inset-y-0 left-0" />

      <!-- Main content -->
      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="max-w-7xl mx-auto px-8 py-6">
            <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Admin</h1>
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

          <!-- Admin Panel -->
          <div v-else class="space-y-6">
            <!-- User Management -->
            <div class="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
              <div class="px-6 py-5 border-b border-gray-200 dark:border-gray-700">
                <div class="flex items-center justify-between">
                  <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100">User Management</h2>
                  <button
                    @click="showNewUserModal = true"
                    class="px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 dark:bg-cyan-700 dark:hover:bg-cyan-800 rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 dark:focus:ring-offset-gray-900"
                  >
                    Add New User
                  </button>
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
                      <th scope="col" class="relative px-6 py-3">
                        <span class="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    <tr v-for="user in sortedAndFilteredUsers" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700">
                      <td class="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                        {{ user.username }}
                      </td>
                      <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300">
                        {{ user.email }}
                      </td>
                      <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                        {{ user.role }}
                      </td>
                      <td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-300 whitespace-nowrap">
                        {{ formatDate(user.created_at) }}
                      </td>
                      <td class="px-6 py-4 text-right text-sm font-medium whitespace-nowrap">
                        <button
                          @click="editUser(user)"
                          class="text-cyan-600 hover:text-cyan-700 dark:text-cyan-400 dark:hover:text-cyan-300 mr-4"
                        >
                          Edit
                        </button>
                        <button
                          @click="resetPassword(user)"
                          class="text-cyan-600 hover:text-cyan-700 dark:text-cyan-400 dark:hover:text-cyan-300 mr-4"
                        >
                          Reset Password
                        </button>
                        <button
                          @click="deleteUser(user)"
                          class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
    
    <!-- User Modal -->
    <UserModal
      :show="showNewUserModal"
      :user="editingUser"
      @close="closeUserModal"
      @saved="handleUserSaved"
    />

    <!-- Password Reset Modal -->
    <PasswordResetModal
      :show="showPasswordResetModal"
      :userId="selectedUserForPasswordReset ? selectedUserForPasswordReset.id : null"
      @close="closePasswordResetModal"
      @saved="handlePasswordResetSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import Sidebar from '../components/Sidebar.vue'
import UserModal from '../components/UserModal.vue'
import PasswordResetModal from '../components/PasswordResetModal.vue'
import { formatDate } from '@/composables/dateUtils'

const router = useRouter()
const authStore = useAuthStore()

const users = ref([])
const loading = ref(true)
const error = ref(null)
const sortKey = ref('username')
const sortOrder = ref('asc')
const showNewUserModal = ref(false)
const editingUser = ref(null)
const settings = ref({
  sessionTimeout: 30
})

const columns = [
  { key: 'username', label: 'Username' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' },
  { key: 'created_at', label: 'Created' }
]

// Password reset state
const showPasswordResetModal = ref(false)
const selectedUserForPasswordReset = ref(null)

const resetPassword = (user) => {
  selectedUserForPasswordReset.value = user
  showPasswordResetModal.value = true
}

const closePasswordResetModal = () => {
  showPasswordResetModal.value = false
  selectedUserForPasswordReset.value = null
}

const handlePasswordResetSaved = () => {
  closePasswordResetModal()
  alert('Password has been reset successfully')
}

onMounted(async () => {
  if (!authStore.isAuthenticated || authStore.user?.role !== 'Admin') {
    router.push('/')
    return
  }

  try {
    const userData = await userService.getUsers()
    users.value = userData
    loading.value = false
  } catch (err) {
    error.value = 'Failed to load users. Please try again later.'
    console.error('Error loading users:', err)
  }
})

const sortBy = (key) => {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

const sortedAndFilteredUsers = computed(() => {
  return [...users.value].sort((a, b) => {
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]

    if (aVal === bVal) return 0
    
    const comparison = aVal > bVal ? 1 : -1
    return sortOrder.value === 'asc' ? comparison : -comparison
  })
})

const editUser = async (user) => {
  editingUser.value = user
  showNewUserModal.value = true
}

const closeUserModal = () => {
  showNewUserModal.value = false
  editingUser.value = null
}

const handleUserSaved = (user) => {
  if (editingUser.value) {
    const index = users.value.findIndex(u => u.id === user.id)
    if (index !== -1) {
      users.value[index] = user
    }
  } else {
    users.value.push(user)
  }
}

const deleteUser = async (user) => {
  if (!confirm(`Are you sure you want to delete user ${user.username}?`)) {
    return
  }

  try {
    await userService.deleteUser(user.id)
    users.value = users.value.filter(u => u.id !== user.id)
  } catch (err) {
    error.value = 'Failed to delete user. Please try again.'
    console.error('Error deleting user:', err)
  }
}

const saveSettings = async () => {
  try {
    // TODO: Implement settings API
  } catch (err) {
    error.value = 'Failed to save settings. Please try again.'
  }
}
</script>
