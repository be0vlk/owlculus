<template>
  <v-card variant="outlined">
    <!-- Header -->
    <v-card-title class="d-flex align-center pa-4 bg-surface">
      <v-icon icon="mdi-account-cog" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <div class="text-h6 font-weight-bold">User Management</div>
        <div class="text-body-2 text-medium-emphasis">Manage system users and their permissions</div>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="primary"
          variant="flat"
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
        <div class="d-flex align-center ga-2">
          <v-chip
            :color="getRoleColor(item.role)"
            size="small"
            variant="tonal"
          >
            {{ item.role }}
          </v-chip>
          <v-chip
            v-if="item.is_superadmin"
            color="orange-darken-2"
            size="small"
            variant="flat"
          >
            <v-icon start size="x-small">mdi-crown</v-icon>
            Superadmin
          </v-chip>
        </div>
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
            v-if="canEditUser(item)"
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
            v-if="canResetPassword(item)"
            color="amber-darken-1"
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
            v-if="canDeleteUser(item)"
            color="error"
            size="small"
            variant="outlined"
            icon
            @click="handleDeleteUser(item)"
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
      @saved="handlePasswordResetSavedWithNotification"
    />
  </v-card>
</template>

<script setup>
import { onMounted } from 'vue'
import { useUsers } from '@/composables/useUsers'
import UserModal from './UserModal.vue'
import PasswordResetModal from './PasswordResetModal.vue'

const emit = defineEmits(['notification', 'confirmDelete'])

const {
  // State
  loading,
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
  handlePasswordResetSaved
} = useUsers()

const handleDeleteUser = (user) => {
  emit('confirmDelete', {
    title: 'Confirm Deletion',
    message: `Are you sure you want to delete the user <strong>${user.username}</strong>?`,
    warning: 'This action cannot be undone. All user data and associated records will be permanently removed.',
    onConfirm: async () => {
      try {
        await deleteUser(user.id)
        emit('notification', { text: `User '${user.username}' deleted successfully`, color: 'success' })
      } catch (err) {
        console.error('Error deleting user:', err)
        emit('notification', { text: 'Failed to delete user. Please try again.', color: 'error' })
        throw err
      }
    }
  })
}

const handlePasswordResetSavedWithNotification = () => {
  handlePasswordResetSaved()
  emit('notification', { text: 'Password has been reset successfully', color: 'success' })
}

onMounted(async () => {
  await loadUsers()
})
</script>

<style scoped>
@import '@/styles/admin-dashboard-table.css';
</style>