<template>
  <v-card :elevation="embedded ? 0 : undefined" :variant="embedded ? 'flat' : 'outlined'">
    <!-- Header -->
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <v-icon v-if="!embedded" icon="mdi-account-cog" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">
          {{ embedded ? 'Users' : 'User Management' }}
        </h2>
        <div v-if="!embedded" class="text-body-medium text-medium-emphasis">
          Manage system users and their permissions
        </div>
      </div>
      <div class="d-flex flex-wrap align-center ga-2">
        <v-btn
          v-if="embedded"
          color="primary"
          variant="flat"
          prepend-icon="mdi-email-plus"
          @click="emit('invite')"
        >
          Invite user
        </v-btn>
        <v-btn
          :color="embedded ? undefined : 'primary'"
          :variant="embedded ? 'outlined' : 'flat'"
          prepend-icon="mdi-account-plus"
          @click="showNewUserModal = true"
        >
          Add User
        </v-btn>
        <v-tooltip text="Refresh user list" location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              icon="mdi-refresh"
              variant="outlined"
              aria-label="Refresh user list"
              @click="loadUsers"
              :loading="loading"
            />
          </template>
        </v-tooltip>
      </div>
    </v-card-title>

    <v-divider />

    <!-- Search Toolbar -->
    <v-card-text class="pa-4">
      <v-row class="mb-0 align-center">
        <v-col cols="12" md="4">
          <v-select
            v-model="roleFilter"
            :items="roleOptions"
            label="Filter by role"
            variant="outlined"
            density="comfortable"
            hide-details
          />
        </v-col>

        <!-- Search Controls -->
        <v-col cols="12" md="8">
          <div class="d-flex align-center ga-4 justify-end">
            <!-- Search Field -->
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search users..."
              variant="outlined"
              density="comfortable"
              hide-details
              class="operations-search"
              clearable
            />
          </div>
        </v-col>
      </v-row>
    </v-card-text>

    <v-divider />

    <v-alert v-if="error" type="error" variant="tonal" class="ma-4">
      {{ error }}
      <v-btn variant="text" @click="loadUsers">Retry</v-btn>
    </v-alert>

    <v-data-table
      v-else
      :cell-props="{ class: 'operations-cell' }"
      :header-props="{ class: 'operations-column' }"
      :headers="tableHeaders"
      :items="filteredUsers"
      :loading="loading"
      item-value="id"
      class="elevation-0 admin-dashboard-table"
      hover
    >
      <template #[`item.username`]="{ item }">
        <div class="py-2" style="min-width: 220px; overflow-wrap: anywhere">
          <div class="font-weight-medium">{{ item.username }}</div>
          <div v-if="embedded" class="text-body-small text-medium-emphasis">{{ item.email }}</div>
        </div>
      </template>

      <!-- Role column -->
      <template #[`item.role`]="{ item }">
        <div class="d-flex align-center ga-2">
          <v-chip :color="getRoleColor(item.role)" size="small" variant="tonal">
            {{ item.role }}
          </v-chip>
          <v-chip v-if="item.is_superadmin" color="orange-darken-2" size="small" variant="flat">
            <v-icon start size="x-small">mdi-crown</v-icon>
            Superadmin
          </v-chip>
        </div>
      </template>

      <!-- Created date -->
      <template #[`item.created_at`]="{ item }">
        <span class="text-body-medium">
          {{ formatDate(item.created_at) }}
        </span>
      </template>

      <!-- Actions column -->
      <template #[`item.actions`]="{ item }">
        <div class="d-flex ga-2">
          <v-btn
            v-if="canEditUser(item)"
            color="info"
            size="small"
            variant="outlined"
            icon
            :aria-label="`Edit ${item.username}`"
            @click="editUser(item)"
          >
            <v-icon>mdi-pencil</v-icon>
            <v-tooltip activator="parent" location="top"> Edit {{ item.username }} </v-tooltip>
          </v-btn>
          <v-menu v-if="canResetPassword(item) || canDeleteUser(item)">
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                icon="mdi-dots-vertical"
                size="small"
                variant="text"
                :aria-label="`More actions for ${item.username}`"
              />
            </template>
            <v-list>
              <v-list-item
                v-if="canResetPassword(item)"
                prepend-icon="mdi-key"
                :title="`Reset password for ${item.username}`"
                @click="resetPassword(item)"
              />
              <v-list-item
                v-if="canDeleteUser(item)"
                prepend-icon="mdi-delete"
                :title="`Delete ${item.username}`"
                @click="handleDeleteUser(item)"
              />
            </v-list>
          </v-menu>
        </div>
      </template>

      <!-- Empty state -->
      <template #no-data>
        <div class="text-center pa-12">
          <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-account-group-outline" size="64" />
          <h3 class="text-title-large font-weight-medium mb-2">
            {{ roleFilter ? 'No users match your filters' : getEmptyStateTitle() }}
          </h3>
          <p class="text-body-medium text-medium-emphasis mb-4">
            {{ roleFilter ? 'Try another role or search term.' : getEmptyStateMessage() }}
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

    <!-- User Modal -->
    <UserModal
      :show="showNewUserModal"
      :user="editingUser"
      @close="closeUserModal"
      @saved="handleUserSavedWithNotification"
    />

    <!-- Password Reset Modal -->
    <PasswordResetModal
      :show="showPasswordResetModal"
      :userId="selectedUserForPasswordReset ? selectedUserForPasswordReset.id : null"
      @close="closePasswordResetModal"
      @saved="handlePasswordResetSavedWithNotification"
    />
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useUsers } from '@/composables/useUsers'
import UserModal from './UserModal.vue'
import PasswordResetModal from './PasswordResetModal.vue'

const props = defineProps({ embedded: Boolean })
const emit = defineEmits(['notification', 'confirmDelete', 'invite', 'count'])

const {
  // State
  users,
  loading,
  error,
  searchQuery,

  // Modal state
  showNewUserModal,
  editingUser,
  showPasswordResetModal,
  selectedUserForPasswordReset,

  // Constants
  vuetifyHeaders,

  // Computed
  sortedAndFilteredUsers,

  // Permission functions
  canDeleteUser,
  canResetPassword,
  canEditUser,

  // Helper functions
  getRoleColor,
  getEmptyStateTitle,
  getEmptyStateMessage,
  shouldShowCreateButton,
  formatDate,

  // CRUD operations
  loadUsers,
  deleteUser,

  // Modal management
  editUser,
  closeUserModal,
  handleUserSaved,
  resetPassword,
  closePasswordResetModal,
  handlePasswordResetSaved,
} = useUsers()

const roleFilter = ref('')
const roleOptions = [
  { title: 'All roles', value: '' },
  { title: 'Admin', value: 'Admin' },
  { title: 'Investigator', value: 'Investigator' },
  { title: 'Analyst', value: 'Analyst' },
]
const filteredUsers = computed(() =>
  sortedAndFilteredUsers.value.filter(
    (user) => !roleFilter.value || user.role === roleFilter.value,
  ),
)
const tableHeaders = computed(() =>
  props.embedded
    ? vuetifyHeaders
        .filter((header) => header.key !== 'email')
        .map((header) => (header.key === 'username' ? { ...header, title: 'User' } : header))
    : vuetifyHeaders,
)
watch([loading, error, () => users.value.length], () => {
  if (!loading.value) emit('count', error.value ? null : users.value.length)
})

const handleDeleteUser = (user) => {
  emit('confirmDelete', {
    title: 'Confirm Deletion',
    message: `Are you sure you want to delete the user <strong>${user.username}</strong>?`,
    warning:
      'This action cannot be undone. All user data and associated records will be permanently removed.',
    onConfirm: async () => {
      try {
        await deleteUser(user.id)
        emit('notification', {
          text: `User '${user.username}' deleted successfully`,
          color: 'success',
        })
      } catch (err) {
        console.error('Error deleting user:', err)
        emit('notification', { text: 'Failed to delete user. Please try again.', color: 'error' })
        throw err
      }
    },
  })
}

const handleUserSavedWithNotification = (user) => {
  handleUserSaved(user)
  emit('notification', { text: `User '${user.username}' saved successfully`, color: 'success' })
}

const handlePasswordResetSavedWithNotification = () => {
  handlePasswordResetSaved()
  emit('notification', { text: 'Password has been reset successfully', color: 'success' })
}

onMounted(async () => {
  await loadUsers()
})
</script>
