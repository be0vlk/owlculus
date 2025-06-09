<template>
  <v-app>
    <Sidebar />

    <v-main>
      <v-container fluid class="pa-6">
        <!-- Page Header Card -->
        <v-card class="mb-6 header-gradient">
          <v-card-title class="d-flex align-center pa-6 text-white">
            <div class="text-h4 font-weight-bold">Admin</div>
          </v-card-title>
        </v-card>


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
          <v-card class="mb-6" variant="outlined">
            <v-card-title class="d-flex align-center pa-4 bg-surface">
              <v-icon icon="mdi-format-list-numbered" color="primary" size="large" class="me-3" />
              <div>
                <div class="text-h6 font-weight-bold">Case Number Configuration</div>
                <div class="text-body-2 text-medium-emphasis">Configure how case numbers are generated</div>
              </div>
            </v-card-title>

            <v-divider />

            <v-card-text class="pa-4">
              <v-container fluid class="pa-0">
                <v-row>
                  <v-col cols="12" lg="6">
                    <v-select
                      v-model="selectedTemplate"
                      :items="templateOptions"
                      item-title="display_name"
                      item-value="value"
                      label="Case Number Format"
                      variant="outlined"
                      density="comfortable"
                      prepend-inner-icon="mdi-format-list-numbered"
                      @update:model-value="onTemplateChange"
                    />
                  </v-col>

                  <v-col cols="12" lg="6" v-if="selectedTemplate === 'PREFIX-YYMM-NN'">
                    <v-text-field
                      v-model="caseNumberPrefix"
                      label="Prefix (2-8 letters/numbers)"
                      variant="outlined"
                      density="comfortable"
                      prepend-inner-icon="mdi-alphabetical-variant"
                      :rules="[validatePrefix]"
                      @input="onPrefixChange"
                      hint="Enter 2-8 alphanumeric characters"
                      persistent-hint
                    />
                  </v-col>
                </v-row>

                <v-row v-if="exampleCaseNumber">
                  <v-col cols="12">
                    <v-card variant="tonal" color="secondary" class="pa-4">
                      <div class="d-flex align-center">
                        <v-icon icon="mdi-eye" color="info" class="me-3" />
                        <div>
                          <div class="text-subtitle-2 font-weight-bold text-info">Preview</div>
                          <div class="text-body-2">
                            Next case will be numbered in the format:
                            <v-chip color="primary" variant="elevated" class="ml-2">
                              {{ exampleCaseNumber }}
                            </v-chip>
                          </div>
                        </div>
                      </div>
                    </v-card>
                  </v-col>
                </v-row>
              </v-container>
            </v-card-text>

            <v-divider />

            <v-card-actions class="pa-4">
              <v-spacer />
              <v-btn
                variant="text"
                prepend-icon="mdi-refresh"
                @click="loadConfiguration"
                :disabled="configLoading"
              >
                Reset
              </v-btn>
              <v-btn
                color="primary"
                variant="flat"
                prepend-icon="mdi-content-save"
                :loading="configLoading"
                :disabled="!isConfigChanged || !isConfigValid"
                @click="saveConfiguration"
              >
                Save Configuration
              </v-btn>
            </v-card-actions>
          </v-card>

          <!-- User Management Card -->
          <v-card variant="outlined">
            <!-- Header -->
            <v-card-title class="d-flex align-center pa-4 bg-surface">
              <v-icon icon="mdi-account-group" color="primary" size="large" class="me-3" />
              <div class="flex-grow-1">
                <div class="text-h6 font-weight-bold">User Management</div>
                <div class="text-body-2 text-medium-emphasis">Manage system users and their permissions</div>
              </div>
              <div class="d-flex align-center ga-2">
                <v-btn
                  v-if="activeTab === 'users'"
                  color="primary"
                  variant="flat"
                  prepend-icon="mdi-account-plus"
                  @click="showNewUserModal = true"
                >
                  Add User
                </v-btn>
                <v-btn
                  v-if="activeTab === 'invites'"
                  color="primary"
                  variant="flat"
                  prepend-icon="mdi-email-plus"
                  @click="showNewInviteModal = true"
                >
                  Generate Invite
                </v-btn>
                <v-tooltip :text="activeTab === 'users' ? 'Refresh user list' : 'Refresh invite list'" location="bottom">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon="mdi-refresh"
                      variant="outlined"
                      @click="activeTab === 'users' ? loadUsers() : loadInvites()"
                      :loading="loading"
                    />
                  </template>
                </v-tooltip>
              </div>
            </v-card-title>

            <v-divider />

            <!-- Tabs -->
            <v-tabs v-model="activeTab" bg-color="surface" class="px-4">
              <v-tab value="users" prepend-icon="mdi-account-group">Users</v-tab>
              <v-tab value="invites" prepend-icon="mdi-email">Invites</v-tab>
            </v-tabs>

            <v-divider />

            <!-- Tab Content -->
            <v-tabs-window v-model="activeTab">
              <!-- Users Tab -->
              <v-tabs-window-item value="users">
                <!-- Search Toolbar -->
                <v-card-text class="pa-4">
                  <v-row align="center" class="mb-0">
                    <v-col cols="12" md="8">
                      <!-- Could add user role filters here in the future -->
                    </v-col>

                    <!-- Search Controls -->
                    <v-col cols="12" md="4">
                      <div class="d-flex align-center ga-4 justify-end">
                        <!-- Search Field -->
                        <v-text-field
                          v-model="searchQuery"
                          prepend-inner-icon="mdi-magnify"
                          label="Search users..."
                          variant="outlined"
                          density="comfortable"
                          hide-details
                          style="min-width: 280px;"
                          clearable
                        />
                      </div>
                    </v-col>
                  </v-row>
                </v-card-text>

                <v-divider />

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
                        Add User
                      </v-btn>
                    </div>
                  </template>
                </v-data-table>
              </v-tabs-window-item>

              <!-- Invites Tab -->
              <v-tabs-window-item value="invites">
                <!-- Search Toolbar -->
                <v-card-text class="pa-4">
                  <v-row align="center" class="mb-0">
                    <v-col cols="12" md="8">
                      <div class="d-flex align-center ga-2">
                        <v-btn
                          color="error"
                          variant="outlined"
                          prepend-icon="mdi-delete-sweep"
                          @click="cleanupExpiredInvites"
                          :loading="cleanupLoading"
                          size="small"
                        >
                          Cleanup Expired
                        </v-btn>
                      </div>
                    </v-col>

                    <!-- Search Controls -->
                    <v-col cols="12" md="4">
                      <div class="d-flex align-center ga-4 justify-end">
                        <!-- Search Field -->
                        <v-text-field
                          v-model="inviteSearchQuery"
                          prepend-inner-icon="mdi-magnify"
                          label="Search invites..."
                          variant="outlined"
                          density="comfortable"
                          hide-details
                          style="min-width: 280px;"
                          clearable
                        />
                      </div>
                    </v-col>
                  </v-row>
                </v-card-text>

                <v-divider />

                <v-data-table
                  :headers="inviteHeaders"
                  :items="sortedAndFilteredInvites"
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

                  <!-- Status column -->
                  <template #[`item.status`]="{ item }">
                    <v-chip
                      :color="getInviteStatusColor(item)"
                      size="small"
                      variant="tonal"
                    >
                      {{ getInviteStatus(item) }}
                    </v-chip>
                  </template>

                  <!-- Created date -->
                  <template #[`item.created_at`]="{ item }">
                    <span class="text-body-2">
                      {{ formatDate(item.created_at) }}
                    </span>
                  </template>

                  <!-- Expires date -->
                  <template #[`item.expires_at`]="{ item }">
                    <span class="text-body-2">
                      {{ formatDate(item.expires_at) }}
                    </span>
                  </template>

                  <!-- Actions column -->
                  <template #[`item.actions`]="{ item }">
                    <div class="d-flex ga-2">
                      <v-btn
                        v-if="!item.is_used && !item.is_expired"
                        color="info"
                        size="small"
                        variant="outlined"
                        icon
                        @click="copyInviteLink(item)"
                      >
                        <v-icon>mdi-content-copy</v-icon>
                        <v-tooltip activator="parent" location="top">
                          Copy invite link
                        </v-tooltip>
                      </v-btn>
                      <v-btn
                        v-if="!item.is_used"
                        color="error"
                        size="small"
                        variant="outlined"
                        icon
                        @click="deleteInvite(item)"
                      >
                        <v-icon>mdi-delete</v-icon>
                        <v-tooltip activator="parent" location="top">
                          Delete invite
                        </v-tooltip>
                      </v-btn>
                    </div>
                  </template>

                  <!-- Empty state -->
                  <template #no-data>
                    <div class="text-center pa-12">
                      <v-icon
                        icon="mdi-email-outline"
                        size="64"
                        color="grey-lighten-1"
                        class="mb-4"
                      />
                      <h3 class="text-h6 font-weight-medium mb-2">
                        {{ getInviteEmptyStateTitle() }}
                      </h3>
                      <p class="text-body-2 text-medium-emphasis mb-4">
                        {{ getInviteEmptyStateMessage() }}
                      </p>
                      <v-btn
                        v-if="shouldShowCreateInviteButton()"
                        color="primary"
                        prepend-icon="mdi-email-plus"
                        @click="showNewInviteModal = true"
                      >
                        Generate Invite
                      </v-btn>
                    </div>
                  </template>
                </v-data-table>
              </v-tabs-window-item>
            </v-tabs-window>
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

    <!-- Invite Modal -->
    <NewInviteModal
      :show="showNewInviteModal"
      @close="closeInviteModal"
      @created="handleInviteCreated"
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
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import api from '@/services/api'
import Sidebar from '../components/Sidebar.vue'
import UserModal from '../components/UserModal.vue'
import NewInviteModal from '../components/NewInviteModal.vue'
import PasswordResetModal from '../components/PasswordResetModal.vue'
import { formatDate } from '@/composables/dateUtils'
import { inviteService } from '@/services/invite'

const router = useRouter()
const authStore = useAuthStore()

const users = ref([])
const invites = ref([])
const loading = ref(true)
const error = ref(null)
const sortKey = ref('username')
const sortOrder = ref('asc')
const showNewUserModal = ref(false)
const showNewInviteModal = ref(false)
const editingUser = ref(null)
const searchQuery = ref('')
const inviteSearchQuery = ref('')
const activeTab = ref('users')
const cleanupLoading = ref(false)

// Vuetify table headers
const vuetifyHeaders = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const inviteHeaders = [
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Expires', key: 'expires_at', sortable: true },
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
    // Load users, invites, and configuration in parallel
    const [userData, inviteData] = await Promise.all([
      userService.getUsers(),
      inviteService.getInvites(),
      loadConfiguration()
    ])

    users.value = userData
    invites.value = inviteData
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

const sortedAndFilteredInvites = computed(() => {
  let filteredInvites = invites.value

  // Apply search filter
  if (inviteSearchQuery.value) {
    const query = inviteSearchQuery.value.toLowerCase()
    filteredInvites = invites.value.filter(invite =>
      (invite.role || '').toLowerCase().includes(query)
    )
  }

  // Sort the filtered results
  return [...filteredInvites].sort((a, b) => {
    const aVal = a.created_at
    const bVal = b.created_at

    if (aVal === bVal) return 0

    const comparison = new Date(aVal) > new Date(bVal) ? 1 : -1
    return -comparison // Default to newest first
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

// Load users function for refresh functionality
const loadUsers = async () => {
  try {
    loading.value = true
    error.value = null
    const userData = await userService.getUsers()
    users.value = userData
  } catch (err) {
    error.value = 'Failed to load users. Please try again later.'
    console.error('Error loading users:', err)
  } finally {
    loading.value = false
  }
}

// Invite-related helper functions
const getInviteStatus = (invite) => {
  if (invite.is_used) return 'Used'
  if (invite.is_expired) return 'Expired'
  return 'Active'
}

const getInviteStatusColor = (invite) => {
  if (invite.is_used) return 'success'
  if (invite.is_expired) return 'error'
  return 'primary'
}

// Invite management functions
const loadInvites = async () => {
  try {
    loading.value = true
    error.value = null
    const inviteData = await inviteService.getInvites()
    invites.value = inviteData
  } catch (err) {
    error.value = 'Failed to load invites. Please try again later.'
    console.error('Error loading invites:', err)
  } finally {
    loading.value = false
  }
}

const closeInviteModal = () => {
  showNewInviteModal.value = false
}

const handleInviteCreated = (invite) => {
  invites.value.unshift(invite)
  showNotification('Invite generated successfully!', 'success')
}

const copyInviteLink = async (invite) => {
  try {
    const baseUrl = window.location.origin
    const inviteLink = `${baseUrl}/register?token=${invite.token}`
    await navigator.clipboard.writeText(inviteLink)
    showNotification('Invite link copied to clipboard!', 'success')
  } catch {
    showNotification('Failed to copy invite link', 'error')
  }
}

const deleteInvite = async (invite) => {
  if (!confirm(`Are you sure you want to delete this ${invite.role} invite?`)) {
    return
  }

  try {
    await inviteService.deleteInvite(invite.id)
    invites.value = invites.value.filter(i => i.id !== invite.id)
    showNotification('Invite deleted successfully', 'success')
  } catch (err) {
    showNotification('Failed to delete invite. Please try again.', 'error')
    console.error('Error deleting invite:', err)
  }
}

const cleanupExpiredInvites = async () => {
  try {
    cleanupLoading.value = true
    const result = await inviteService.cleanupExpiredInvites()
    await loadInvites() // Refresh the list
    showNotification(`Cleaned up ${result.deleted_count || 0} expired invites`, 'success')
  } catch (err) {
    showNotification('Failed to cleanup expired invites', 'error')
    console.error('Error cleaning up expired invites:', err)
  } finally {
    cleanupLoading.value = false
  }
}

// Invite empty state functions
const getInviteEmptyStateTitle = () => {
  if (inviteSearchQuery.value) {
    return 'No invites found'
  } else if ((invites.value || []).length === 0) {
    return 'No invites yet'
  } else {
    return 'No invites match your search'
  }
}

const getInviteEmptyStateMessage = () => {
  if (inviteSearchQuery.value) {
    return 'Try adjusting your search terms to find the invite you\'re looking for.'
  } else if ((invites.value || []).length === 0) {
    return 'Generate your first invite to allow new users to register.'
  } else {
    return 'Try adjusting your search to see more invites.'
  }
}

const shouldShowCreateInviteButton = () => {
  return (invites.value || []).length === 0 && !inviteSearchQuery.value
}
</script>

<style scoped>
.header-gradient {
  background: linear-gradient(135deg, rgb(var(--v-theme-primary)) 0%, rgb(var(--v-theme-primary), 0.8) 100%) !important;
}

.admin-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.admin-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.admin-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}

.admin-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>
