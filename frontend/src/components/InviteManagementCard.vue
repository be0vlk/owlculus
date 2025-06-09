<template>
  <v-card variant="outlined">
    <!-- Header -->
    <v-card-title class="d-flex align-center pa-4 bg-surface">
      <v-icon icon="mdi-email" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <div class="text-h6 font-weight-bold">Invite Management</div>
        <div class="text-body-2 text-medium-emphasis">Manage user invitation links</div>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-email-plus"
          @click="showNewInviteModal = true"
        >
          Generate Invite
        </v-btn>
        <v-tooltip text="Refresh invite list" location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              icon="mdi-refresh"
              variant="outlined"
              @click="loadInvites"
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
          <div class="d-flex align-center ga-2">
            <v-btn
              color="error"
              variant="outlined"
              prepend-icon="mdi-delete-sweep"
              @click="handleCleanupExpiredInvites"
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
            @click="handleCopyInviteLink(item)"
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
            @click="handleDeleteInvite(item)"
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

    <!-- Invite Modal -->
    <NewInviteModal
      :show="showNewInviteModal"
      @close="closeInviteModal"
      @created="handleInviteCreatedWithNotification"
    />
  </v-card>
</template>

<script setup>
import { onMounted } from 'vue'
import { useInvites } from '@/composables/useInvites'
import NewInviteModal from './NewInviteModal.vue'

const emit = defineEmits(['notification', 'confirmDelete'])

const {
  // State
  loading,
  inviteSearchQuery,
  cleanupLoading,
  
  // Modal state
  showNewInviteModal,
  
  // Constants
  inviteHeaders,
  
  // Computed
  sortedAndFilteredInvites,
  
  // Helper functions
  getRoleColor,
  getInviteStatus,
  getInviteStatusColor,
  getInviteEmptyStateTitle,
  getInviteEmptyStateMessage,
  shouldShowCreateInviteButton,
  formatDate,
  
  // CRUD operations
  loadInvites,
  deleteInvite,
  cleanupExpiredInvites,
  copyInviteLink,
  
  // Modal management
  closeInviteModal,
  handleInviteCreated
} = useInvites()

const handleCopyInviteLink = async (invite) => {
  try {
    await copyInviteLink(invite)
    emit('notification', { text: 'Invite link copied to clipboard!', color: 'success' })
  } catch {
    emit('notification', { text: 'Failed to copy invite link', color: 'error' })
  }
}

const handleDeleteInvite = (invite) => {
  emit('confirmDelete', {
    title: 'Confirm Deletion',
    message: `Are you sure you want to delete this ${invite.role} invite?`,
    onConfirm: async () => {
      try {
        await deleteInvite(invite)
        emit('notification', { text: 'Invite deleted successfully', color: 'success' })
      } catch (err) {
        emit('notification', { text: 'Failed to delete invite. Please try again.', color: 'error' })
        throw err
      }
    }
  })
}

const handleCleanupExpiredInvites = async () => {
  try {
    const result = await cleanupExpiredInvites()
    emit('notification', { text: `Cleaned up ${result.deleted_count || 0} expired invites`, color: 'success' })
  } catch (err) {
    emit('notification', { text: 'Failed to cleanup expired invites', color: 'error' })
    console.error('Error cleaning up expired invites:', err)
  }
}

const handleInviteCreatedWithNotification = (invite) => {
  handleInviteCreated(invite)
  emit('notification', { text: 'Invite generated successfully!', color: 'success' })
}

onMounted(async () => {
  await loadInvites()
})
</script>

<style scoped>
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