<template>
  <v-card :elevation="embedded ? 0 : undefined" :variant="embedded ? 'flat' : 'outlined'">
    <!-- Header -->
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <v-icon v-if="!embedded" icon="mdi-email" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">
          {{ embedded ? 'Invites' : 'Invite Management' }}
        </h2>
        <div v-if="!embedded" class="text-body-medium text-medium-emphasis">
          Manage user invitation links
        </div>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn
          size="small"
          ref="inviteAction"
          color="primary"
          variant="flat"
          prepend-icon="mdi-email-plus"
          @click="openCreateDialog"
        >
          {{ embedded ? 'Invite user' : 'Generate Invite' }}
        </v-btn>
        <v-tooltip text="Refresh invite list" location="bottom">
          <template #activator="{ props }">
            <v-btn
              size="small"
              v-bind="props"
              icon="mdi-refresh"
              variant="outlined"
              aria-label="Refresh invite list"
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
      <v-row class="mb-0 align-center">
        <v-col cols="12" md="4">
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

        <v-col cols="12" md="4">
          <v-select
            v-model="statusFilter"
            :items="statusOptions"
            label="Invitation status"
            variant="outlined"
            density="comfortable"
            hide-details
          />
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
      <v-btn variant="text" @click="loadInvites">Retry</v-btn>
    </v-alert>

    <v-data-table
      v-else
      :cell-props="{ class: 'operations-cell' }"
      :header-props="{ class: 'operations-column' }"
      :headers="inviteHeaders"
      :items="filteredInvites"
      :loading="loading"
      item-value="id"
      class="elevation-0 admin-dashboard-table"
      hover
    >
      <!-- Role column -->
      <template #[`item.role`]="{ item }">
        <v-chip :color="getRoleColor(item.role)" size="small" variant="tonal">
          {{ item.role }}
        </v-chip>
      </template>

      <!-- Status column -->
      <template #[`item.status`]="{ item }">
        <v-chip :color="getInviteStatusColor(item)" size="small" variant="tonal">
          {{ getInviteStatus(item) === 'Active' ? 'Pending' : getInviteStatus(item) }}
        </v-chip>
      </template>

      <!-- Created date -->
      <template #[`item.created_at`]="{ item }">
        <span class="text-body-medium">
          {{ formatDate(item.created_at) }}
        </span>
      </template>

      <!-- Expires date -->
      <template #[`item.expires_at`]="{ item }">
        <span class="text-body-medium">
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
            aria-label="Copy invite link"
          >
            <v-icon>mdi-content-copy</v-icon>
            <v-tooltip activator="parent" location="top"> Copy invite link </v-tooltip>
          </v-btn>
          <v-btn
            v-if="!item.is_used"
            color="error"
            size="small"
            variant="outlined"
            icon
            @click="handleDeleteInvite(item)"
            aria-label="Delete invite"
          >
            <v-icon>mdi-delete</v-icon>
            <v-tooltip activator="parent" location="top"> Delete invite </v-tooltip>
          </v-btn>
        </div>
      </template>

      <!-- Empty state -->
      <template #no-data>
        <div class="text-center pa-12">
          <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-email-outline" size="64" />
          <h3 class="text-title-large font-weight-medium mb-2">
            {{ statusFilter === 'all' ? getInviteEmptyStateTitle() : `No ${statusFilter} invites` }}
          </h3>
          <p class="text-body-medium text-medium-emphasis mb-4">
            {{
              statusFilter === 'all'
                ? getInviteEmptyStateMessage()
                : 'Try another status or search term, or invite someone new.'
            }}
          </p>
          <v-btn
            v-if="shouldShowCreateInviteButton()"
            color="primary"
            prepend-icon="mdi-email-plus"
            @click="openCreateDialog"
          >
            {{ embedded ? 'Invite user' : 'Generate Invite' }}
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
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useInvites } from '@/composables/useInvites'
import NewInviteModal from './NewInviteModal.vue'

defineProps({ embedded: Boolean })
const emit = defineEmits(['notification', 'confirmDelete', 'count'])

const {
  // State
  invites,
  loading,
  error,
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
  handleInviteCreated,
} = useInvites()

const statusFilter = ref('pending')
const statusOptions = [
  { title: 'Pending', value: 'pending' },
  { title: 'Expired', value: 'expired' },
  { title: 'All invitations', value: 'all' },
]
const pendingCount = computed(
  () => invites.value.filter((invite) => !invite.is_used && !invite.is_expired).length,
)
const filteredInvites = computed(() =>
  sortedAndFilteredInvites.value.filter((invite) => {
    if (statusFilter.value === 'pending') return !invite.is_used && !invite.is_expired
    if (statusFilter.value === 'expired') return !invite.is_used && invite.is_expired
    return true
  }),
)
watch([loading, error, pendingCount], () => {
  if (!loading.value) emit('count', error.value ? null : pendingCount.value)
})

const inviteAction = ref(null)
let inviteOrigin = null
const openCreateDialog = (event) => {
  inviteOrigin = event?.currentTarget || inviteAction.value?.$el
  showNewInviteModal.value = true
}
watch(showNewInviteModal, async (show, wasOpen) => {
  if (!show && wasOpen) {
    await nextTick()
    inviteOrigin?.focus()
  }
})
defineExpose({ openCreateDialog })

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
    },
  })
}

const handleCleanupExpiredInvites = async () => {
  try {
    const result = await cleanupExpiredInvites()
    emit('notification', {
      text: `Cleaned up ${result.deleted_count || 0} expired invites`,
      color: 'success',
    })
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
