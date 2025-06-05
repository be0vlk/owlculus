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

        <!-- Main Content -->
        <div v-else>
          <!-- Case Number Configuration Card -->
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center">
              <v-icon icon="mdi-format-list-numbered" class="me-2" />
              Case Number Configuration
            </v-card-title>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="selectedTemplate"
                    :items="templateOptions"
                    item-title="display_name"
                    item-value="value"
                    label="Case Number Format"
                    variant="outlined"
                    density="compact"
                    @update:model-value="onTemplateChange"
                  />
                </v-col>
                
                <v-col cols="12" md="6" v-if="selectedTemplate === 'PREFIX-YYMM-NN'">
                  <v-text-field
                    v-model="caseNumberPrefix"
                    label="Prefix (2-8 letters/numbers)"
                    variant="outlined"
                    density="compact"
                    :rules="[validatePrefix]"
                    @input="onPrefixChange"
                  />
                </v-col>
              </v-row>
              
              <v-row v-if="exampleCaseNumber">
                <v-col cols="12">
                  <v-alert
                    type="info"
                    variant="tonal"
                    density="compact"
                  >
                    <template #text>
                      <strong>Preview:</strong> Next case will be numbered like: 
                      <code class="text-primary">{{ exampleCaseNumber }}</code>
                    </template>
                  </v-alert>
                </v-col>
              </v-row>
              
              <v-row>
                <v-col cols="12" class="d-flex justify-end">
                  <v-btn
                    color="primary"
                    :loading="configLoading"
                    :disabled="!isConfigChanged || !isConfigValid"
                    @click="saveConfiguration"
                  >
                    Save Configuration
                  </v-btn>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- User Management Table -->
          <v-card>
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
                {{ formatDate(item.created_at) }}
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
        </div>
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

    <!-- Snackbar for notifications -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="snackbar.timeout"
      location="top right"
    >
      {{ snackbar.text }}
      <template #actions>
        <v-btn
          variant="text"
          @click="snackbar.show = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import api from '@/services/api'
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

// Configuration state
const selectedTemplate = ref('YYMM-NN')
const caseNumberPrefix = ref('')
const originalTemplate = ref('YYMM-NN')
const originalPrefix = ref('')
const configLoading = ref(false)
const exampleCaseNumber = ref('')

// Snackbar state
const snackbar = ref({
  show: false,
  text: '',
  color: 'success',
  timeout: 4000
})

const templateOptions = [
  { display_name: 'Monthly Reset (YYMM-NN)', value: 'YYMM-NN' },
  { display_name: 'Prefix + Monthly Reset (PREFIX-YYMM-NN)', value: 'PREFIX-YYMM-NN' }
]

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
  showNotification('Password has been reset successfully', 'success')
}

// Snackbar helper function
const showNotification = (text, color = 'success') => {
  snackbar.value.text = text
  snackbar.value.color = color
  snackbar.value.show = true
}

// Configuration computed properties
const isConfigChanged = computed(() => {
  return selectedTemplate.value !== originalTemplate.value || 
         caseNumberPrefix.value !== originalPrefix.value
})

const isConfigValid = computed(() => {
  if (selectedTemplate.value === 'PREFIX-YYMM-NN') {
    return validatePrefix(caseNumberPrefix.value) === true
  }
  return true
})

// Configuration methods
const validatePrefix = (value) => {
  if (selectedTemplate.value === 'PREFIX-YYMM-NN') {
    if (!value) return 'Prefix is required'
    if (!/^[A-Za-z0-9]{2,8}$/.test(value)) {
      return 'Prefix must be 2-8 alphanumeric characters'
    }
  }
  return true
}

const onTemplateChange = async () => {
  if (selectedTemplate.value !== 'PREFIX-YYMM-NN') {
    caseNumberPrefix.value = ''
  }
  await updatePreview()
}

const onPrefixChange = async () => {
  await updatePreview()
}

const updatePreview = async () => {
  if (!isConfigValid.value) {
    exampleCaseNumber.value = ''
    return
  }
  
  try {
    const params = new URLSearchParams({
      template: selectedTemplate.value
    })
    
    if (selectedTemplate.value === 'PREFIX-YYMM-NN' && caseNumberPrefix.value) {
      params.append('prefix', caseNumberPrefix.value)
    }
    
    const response = await api.get(`/api/admin/configuration/preview?${params}`)
    exampleCaseNumber.value = response.data.example_case_number
  } catch (error) {
    console.error('Error updating preview:', error)
    exampleCaseNumber.value = ''
  }
}

const loadConfiguration = async () => {
  try {
    const response = await api.get('/api/admin/configuration')
    const config = response.data
    
    selectedTemplate.value = config.case_number_template
    caseNumberPrefix.value = config.case_number_prefix || ''
    originalTemplate.value = config.case_number_template
    originalPrefix.value = config.case_number_prefix || ''
    
    await updatePreview()
  } catch (error) {
    console.error('Error loading configuration:', error)
  }
}

const saveConfiguration = async () => {
  if (!isConfigValid.value) return
  
  configLoading.value = true
  try {
    const configData = {
      case_number_template: selectedTemplate.value,
      case_number_prefix: selectedTemplate.value === 'PREFIX-YYMM-NN' ? caseNumberPrefix.value : null
    }
    
    await api.put('/api/admin/configuration', configData)
    
    originalTemplate.value = selectedTemplate.value
    originalPrefix.value = caseNumberPrefix.value
    
    showNotification('Configuration saved successfully!', 'success')
  } catch (error) {
    console.error('Error saving configuration:', error)
    showNotification('Failed to save configuration. Please try again.', 'error')
  } finally {
    configLoading.value = false
  }
}

onMounted(async () => {
  if (!authStore.isAuthenticated || authStore.user?.role !== 'Admin') {
    router.push('/')
    return
  }

  try {
    // Load both users and configuration in parallel
    const [userData] = await Promise.all([
      userService.getUsers(),
      loadConfiguration()
    ])
    
    users.value = userData
    loading.value = false
  } catch (err) {
    error.value = 'Failed to load admin data. Please try again later.'
    console.error('Error loading admin data:', err)
    loading.value = false
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