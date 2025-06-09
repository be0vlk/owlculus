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
          <!-- System Configuration -->
          <SystemConfigurationCard @notification="handleNotification" />

          <!-- User and Invite Management -->
          <v-card variant="outlined">
            <!-- Header -->
            <v-card-title class="d-flex align-center pa-4 bg-surface">
              <v-icon icon="mdi-account-group" color="primary" size="large" class="me-3" />
              <div class="flex-grow-1">
                <div class="text-h6 font-weight-bold">User Management</div>
                <div class="text-body-2 text-medium-emphasis">Manage system users and their permissions</div>
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
                <UserManagementCard 
                  @notification="handleNotification"
                  @confirmDelete="handleConfirmDelete"
                />
              </v-tabs-window-item>

              <!-- Invites Tab -->
              <v-tabs-window-item value="invites">
                <InviteManagementCard 
                  @notification="handleNotification"
                  @confirmDelete="handleConfirmDelete"
                />
              </v-tabs-window-item>
            </v-tabs-window>
          </v-card>
        </div>
      </v-container>
    </v-main>

    <!-- Confirmation Dialog -->
    <ConfirmationDialog ref="confirmDialog" />

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
          @click="closeNotification"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables/useNotifications'
import Sidebar from '@/components/Sidebar.vue'
import SystemConfigurationCard from '@/components/SystemConfigurationCard.vue'
import UserManagementCard from '@/components/UserManagementCard.vue'
import InviteManagementCard from '@/components/InviteManagementCard.vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'

const router = useRouter()
const authStore = useAuthStore()

// State
const loading = ref(true)
const error = ref(null)
const activeTab = ref('users')

// Notifications
const { snackbar, showNotification, closeNotification } = useNotifications()

// Confirmation dialog reference
const confirmDialog = ref(null)

// Event handlers
const handleNotification = ({ text, color }) => {
  showNotification(text, color)
}

const handleConfirmDelete = async ({ title, message, warning, onConfirm }) => {
  try {
    await confirmDialog.value.confirm({
      title,
      message,
      warning,
      confirmText: 'Delete',
      confirmColor: 'error',
      icon: 'mdi-delete-alert',
      iconColor: 'error'
    })
    
    // Execute the confirmation action
    await onConfirm()
  } catch (error) {
    // User cancelled or action failed
    console.log('Delete action cancelled or failed')
  }
}

onMounted(async () => {
  if (!authStore.isAuthenticated || authStore.user?.role !== 'Admin') {
    router.push('/')
    return
  }

  // Let child components handle their own loading
  loading.value = false
})
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
