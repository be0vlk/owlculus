<template>
  <v-card :elevation="0" variant="flat">
    <!-- Header -->
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">Users</h2>
      </div>
      <div class="d-flex flex-wrap align-center ga-2">
        <v-btn
          size="small"
          color="primary"
          variant="flat"
          prepend-icon="mdi-email-plus"
          @click="emit('invite')"
        >
          Invite user
        </v-btn>
        <v-btn
          size="small"
          variant="outlined"
          prepend-icon="mdi-account-plus"
          @click="showNewUserModal = true"
        >
          Add User
        </v-btn>
        <v-tooltip text="Refresh user list" location="bottom">
          <template #activator="{ props }">
            <v-btn
              size="small"
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
      :headers="headers"
      :items="filteredUsers"
      :search="searchQuery"
      :sort-by="[{ key: 'username', order: 'asc' }]"
      :loading="loading"
      item-value="id"
      class="elevation-0 admin-dashboard-table"
      hover
    >
      <template #[`item.username`]="{ item }">
        <div class="py-2" style="min-width: 220px; overflow-wrap: anywhere">
          <div class="font-weight-medium">{{ userDisplayName(item) }}</div>
          <div class="text-body-small text-medium-emphasis">{{ item.email }}</div>
        </div>
      </template>

      <!-- Role column -->
      <template #[`item.role`]="{ item }">
        <div class="d-flex align-center ga-2">
          <v-chip color="grey-darken-1" size="small" variant="tonal">
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
            {{
              roleFilter
                ? 'No users match your filters'
                : searchQuery
                  ? 'No users found'
                  : 'No users yet'
            }}
          </h3>
          <p class="text-body-medium text-medium-emphasis mb-4">
            {{
              roleFilter
                ? 'Try another role or search term.'
                : searchQuery
                  ? "Try adjusting your search terms to find the user you're looking for."
                  : 'Get started by adding your first user to begin managing the system.'
            }}
          </p>
          <v-btn
            v-if="!users.length && !searchQuery"
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
      :userId="selectedUserForPasswordReset?.id ?? null"
      @close="closePasswordResetModal"
      @saved="handlePasswordResetSaved"
    />
  </v-card>
</template>

<script setup>
import { userDisplayName } from '@/utils/userDisplay'
import { computed, onMounted, ref, watch } from 'vue'
import { formatDate } from '@/composables/dateUtils'
import { userService } from '@/services/user'
import { useAuthStore } from '@/stores/auth'
import UserModal from './UserModal.vue'
import PasswordResetModal from './PasswordResetModal.vue'

const emit = defineEmits(['notification', 'confirmDelete', 'invite', 'count'])
const authStore = useAuthStore()

const users = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const showNewUserModal = ref(false)
const editingUser = ref(null)
const showPasswordResetModal = ref(false)
const selectedUserForPasswordReset = ref(null)

const headers = [
  // The email is searched and shown under the username.
  { title: 'User', key: 'username', value: (user) => `${user.username} ${user.email}` },
  { title: 'Role', key: 'role' },
  { title: 'Created', key: 'created_at' },
  { title: 'Actions', key: 'actions', sortable: false },
]

const roleFilter = ref('')
const roleOptions = [
  { title: 'All roles', value: '' },
  { title: 'Admin', value: 'Admin' },
  { title: 'Investigator', value: 'Investigator' },
  { title: 'Analyst', value: 'Analyst' },
]
const filteredUsers = computed(() =>
  users.value.filter((user) => !roleFilter.value || user.role === roleFilter.value),
)
watch([loading, error, () => users.value.length], () => {
  if (!loading.value) emit('count', error.value ? null : users.value.length)
})

// Permission checks
const canDeleteUser = (targetUser) => {
  const currentUser = authStore.user
  if (!currentUser || targetUser.system_identity) return false
  // Cannot delete yourself or superadmins; only superadmins delete admins
  if (currentUser.id === targetUser.id || targetUser.is_superadmin) return false
  return targetUser.role !== 'Admin' || !!currentUser.is_superadmin
}

// Only superadmins edit or reset superadmins
const canEditUser = (targetUser) => {
  const currentUser = authStore.user
  if (!currentUser || targetUser.system_identity) return false
  return !targetUser.is_superadmin || !!currentUser.is_superadmin
}
const canResetPassword = canEditUser

const loadUsers = async () => {
  try {
    loading.value = true
    error.value = null
    users.value = await userService.getUsers()
  } catch (err) {
    error.value = 'Failed to load users. Please try again later.'
    console.error('Error loading users:', err)
  } finally {
    loading.value = false
  }
}

const editUser = (user) => {
  editingUser.value = user
  showNewUserModal.value = true
}

const closeUserModal = () => {
  showNewUserModal.value = false
  editingUser.value = null
}

const handleUserSaved = (user) => {
  if (editingUser.value) {
    const index = users.value.findIndex((u) => u.id === user.id)
    if (index !== -1) users.value[index] = user
  } else {
    users.value.push(user)
  }
  closeUserModal()
  emit('notification', {
    text: `User '${userDisplayName(user)}' saved successfully`,
    color: 'success',
  })
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
  emit('notification', { text: 'Password has been reset successfully', color: 'success' })
}

const handleDeleteUser = (user) => {
  emit('confirmDelete', {
    title: 'Confirm Deletion',
    message: `Are you sure you want to delete the user "${userDisplayName(user)}"?`,
    warning:
      'This action cannot be undone. All user data and associated records will be permanently removed.',
    onConfirm: async () => {
      try {
        await userService.deleteUser(user.id)
        users.value = users.value.filter((u) => u.id !== user.id)
        emit('notification', {
          text: `User '${userDisplayName(user)}' deleted successfully`,
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

onMounted(loadUsers)
</script>
