<template>
  <BaseDashboard :error="error" :loading="loading" title="Admin">
    <!-- Main Content -->
    <!-- User and Invite Management -->
    <v-card class="mb-6" variant="outlined">
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-account-group" size="large" />
        <div class="flex-grow-1">
          <div class="text-h6 font-weight-bold">User Management</div>
          <div class="text-body-2 text-medium-emphasis">
            Manage system users and their permissions
          </div>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Tabs -->
      <v-tabs v-model="activeTab" bg-color="surface" class="px-4">
        <v-tab prepend-icon="mdi-account" value="users">Users</v-tab>
        <v-tab prepend-icon="mdi-email" value="invites">Invites</v-tab>
      </v-tabs>

      <v-divider />

      <!-- Tab Content -->
      <v-tabs-window v-model="activeTab">
        <!-- Users Tab -->
        <v-tabs-window-item value="users">
          <UserManagementCard
            @confirmDelete="handleConfirmDelete"
            @notification="handleNotification"
          />
        </v-tabs-window-item>

        <!-- Invites Tab -->
        <v-tabs-window-item value="invites">
          <InviteManagementCard
            @confirmDelete="handleConfirmDelete"
            @notification="handleNotification"
          />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card>

    <!-- API Key Management -->
    <ApiKeyManagementCard @confirmDelete="handleConfirmDelete" @notification="handleNotification" />

    <!-- System Configuration -->
    <SystemConfigurationCard @notification="handleNotification" />

    <!-- Evidence Template Management -->
    <EvidenceTemplateManagementCard @notification="handleNotification" />

    <!-- Task Template Management -->
    <TaskTemplateManagementCard
      @notification="handleNotification"
      @confirmDelete="handleConfirmDelete"
    />
  </BaseDashboard>

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
      <v-btn variant="text" @click="closeNotification"> Close </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables/useNotifications'
import BaseDashboard from '@/components/BaseDashboard.vue'
import SystemConfigurationCard from '@/components/SystemConfigurationCard.vue'
import ApiKeyManagementCard from '@/components/ApiKeyManagementCard.vue'
import EvidenceTemplateManagementCard from '@/components/EvidenceTemplateManagementCard.vue'
import TaskTemplateManagementCard from '@/components/TaskTemplateManagementCard.vue'
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
      iconColor: 'error',
    })

    // Execute the confirmation action
    await onConfirm()
  } catch {
    // User cancelled or action failed
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
@import '@/styles/admin-dashboard-table.css';
</style>
