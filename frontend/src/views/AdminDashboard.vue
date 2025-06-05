<template>
  <v-app>
    <Sidebar />
    
    <v-main>
      <v-container class="pa-6">
        <!-- Page Header -->
        <div class="mb-6">
          <v-row align="center" justify="space-between">
            <v-col>
              <h1 class="text-h4 font-weight-bold">
                Admin Dashboard
              </h1>
            </v-col>
            <v-col cols="auto">
              <v-btn
                color="primary"
                prepend-icon="mdi-account-plus"
                @click="showNewUserModal = true"
              >
                Add New User
              </v-btn>
            </v-col>
          </v-row>
        </div>

        <!-- Loading state -->
        <v-card v-if="loading">
          <v-card-title class="d-flex align-center justify-end pa-6">
            <v-skeleton-loader type="text" width="300" />
          </v-card-title>
          <v-skeleton-loader 
            type="table" 
            class="ma-4"
          />
        </v-card>

        <!-- Error state -->
        <v-alert
          v-else-if="error"
          type="error"
          class="ma-4"
          :text="error"
          prominent
          border="start"
        />

        <!-- User Management Table -->
        <v-card v-else>
          <v-card-title class="d-flex align-center justify-end">
            <!-- Search Field -->
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search users..."
              variant="outlined"
              density="compact"
              hide-details
              style="min-width: 300px;"
            />
          </v-card-title>

          <v-data-table
            :headers="vuetifyHeaders"
            :items="sortedAndFilteredUsers"
            :loading="loading"
            item-key="id"
            class="elevation-0 admin-dashboard-table"
            hover
          >
            <!-- Role column -->
            <template #[`item.role`]="{ item }">
              <v-chip
                :color="getRoleColor(item.role)"
                size="small"
                variant="tonal"
              >
                {{ item.role }}
              </v-chip>
            </template>

            <!-- Created date -->
            <template #[`item.created_at`]="{ item }">
              <span class="text-body-2">
                {{ formatRelativeDate(item.created_at) }}
                <v-tooltip activator="parent" location="top">
                  {{ formatDate(item.created_at) }}
                </v-tooltip>
              </span>
            </template>

            <!-- Actions column -->
            <template #[`item.actions`]="{ item }">
              <div class="d-flex ga-2">
                <v-btn
                  color="info"
                  size="small"
                  variant="outlined"
                  icon
                  @click="editUser(item)"
                >
                  <v-icon>mdi-pencil</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Edit {{ item.username }}
                  </v-tooltip>
                </v-btn>
                <v-btn
                  color="warning"
                  size="small"
                  variant="outlined"
                  icon
                  @click="resetPassword(item)"
                >
                  <v-icon>mdi-key</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Reset password for {{ item.username }}
                  </v-tooltip>
                </v-btn>
                <v-btn
                  color="error"
                  size="small"
                  variant="outlined"
                  icon
                  @click="deleteUser(item)"
                >
                  <v-icon>mdi-delete</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Delete {{ item.username }}
                  </v-tooltip>
                </v-btn>
              </div>
            </template>

            <!-- Empty state -->
            <template #no-data>
              <div class="text-center pa-12">
                <v-icon
                  icon="mdi-account-group-outline"
                  size="64"
                  color="grey-lighten-1"
                  class="mb-4"
                />
                <h3 class="text-h6 font-weight-medium mb-2">
                  {{ getEmptyStateTitle() }}
                </h3>
                <p class="text-body-2 text-medium-emphasis mb-4">
                  {{ getEmptyStateMessage() }}
                </p>
                <v-btn
                  v-if="shouldShowCreateButton()"
                  color="primary"
                  prepend-icon="mdi-account-plus"
                  @click="showNewUserModal = true"
                >
                  Add First User
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-container>
    </v-main>
    
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
  </v-app>
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
import { formatDistanceToNow } from 'date-fns'

const router = useRouter()
const authStore = useAuthStore()

const users = ref([])
const loading = ref(true)
const error = ref(null)
const sortKey = ref('username')
const sortOrder = ref('asc')
const showNewUserModal = ref(false)
const editingUser = ref(null)
const searchQuery = ref('')

// Vuetify table headers
const vuetifyHeaders = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

// Password reset state
const showPasswordResetModal = ref(false)
const selectedUserForPasswordReset = ref(null)

const getRoleColor = (role) => {
  switch (role) {
    case 'Admin': return 'error'
    case 'Investigator': return 'primary'
    case 'Analyst': return 'info'
    default: return 'default'
  }
}

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


const sortedAndFilteredUsers = computed(() => {
  let filteredUsers = users.value

  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filteredUsers = users.value.filter(user =>
      (user.username || '').toLowerCase().includes(query) ||
      (user.email || '').toLowerCase().includes(query) ||
      (user.role || '').toLowerCase().includes(query)
    )
  }

  // Sort the filtered results
  return [...filteredUsers].sort((a, b) => {
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
  } catch {
    error.value = 'Failed to delete user. Please try again.'
  }
}

// Function to format relative dates
const formatRelativeDate = (dateString) => {
  if (!dateString) return 'N/A'
  try {
    // Parse the datetime string directly - backend provides ISO format with timezone
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch (error) {
    console.error('Error formatting relative date:', error)
    return 'Invalid date'
  }
}

// Empty state functions
const getEmptyStateTitle = () => {
  if (searchQuery.value) {
    return 'No users found'
  } else if ((users.value || []).length === 0) {
    return 'No users yet'
  } else {
    return 'No users match your search'
  }
}

const getEmptyStateMessage = () => {
  if (searchQuery.value) {
    return 'Try adjusting your search terms to find the user you\'re looking for.'
  } else if ((users.value || []).length === 0) {
    return 'Get started by adding your first user to begin managing the system.'
  } else {
    return 'Try adjusting your search to see more users.'
  }
}

const shouldShowCreateButton = () => {
  return (users.value || []).length === 0 && !searchQuery.value
}
</script>

<style scoped>
.admin-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.admin-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08) !important;
}

.admin-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgba(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgba(var(--v-theme-on-surface), 0.12) !important;
}

.admin-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>