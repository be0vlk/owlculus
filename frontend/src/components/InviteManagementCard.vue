<template>
  <v-card :elevation="0" variant="flat">
    <!-- Header -->
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">Invites</h2>
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
          Invite user
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
              v-model="searchQuery"
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
      :headers="headers"
      :items="filteredInvites"
      :search="searchQuery"
      :sort-by="[{ key: 'created_at', order: 'desc' }]"
      :loading="loading"
      item-value="id"
      class="elevation-0 admin-dashboard-table"
      hover
    >
      <!-- Role column -->
      <template #[`item.role`]="{ item }">
        <v-chip color="grey-darken-1" size="small" variant="tonal">
          {{ item.role }}
        </v-chip>
      </template>

      <!-- Status column -->
      <template #[`item.status`]="{ item }">
        <v-chip :color="inviteStatus(item).color" size="small" variant="tonal">
          {{ inviteStatus(item).label }}
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
            {{
              statusFilter !== 'all'
                ? `No ${statusFilter} invites`
                : searchQuery
                  ? 'No invites found'
                  : 'No invites yet'
            }}
          </h3>
          <p class="text-body-medium text-medium-emphasis mb-4">
            {{
              statusFilter !== 'all'
                ? 'Try another status or search term, or invite someone new.'
                : searchQuery
                  ? "Try adjusting your search terms to find the invite you're looking for."
                  : 'Generate your first invite to allow new users to register.'
            }}
          </p>
          <v-btn
            v-if="!invites.length && !searchQuery"
            color="primary"
            prepend-icon="mdi-email-plus"
            @click="openCreateDialog"
          >
            Invite user
          </v-btn>
        </div>
      </template>
    </v-data-table>

    <!-- Invite Modal -->
    <NewInviteModal
      :show="showNewInviteModal"
      @close="showNewInviteModal = false"
      @created="handleInviteCreated"
    />
  </v-card>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { formatDate } from '@/composables/dateUtils'
import { inviteService } from '@/services/invite'
import NewInviteModal from './NewInviteModal.vue'

const emit = defineEmits(['notification', 'confirmDelete', 'count'])

const invites = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const cleanupLoading = ref(false)
const showNewInviteModal = ref(false)

const headers = [
  { title: 'Role', key: 'role' },
  { title: 'Status', key: 'status' },
  { title: 'Created', key: 'created_at' },
  { title: 'Expires', key: 'expires_at' },
  { title: 'Actions', key: 'actions', sortable: false },
]

const inviteStatus = (invite) => {
  if (invite.is_used) return { label: 'Used', color: 'success' }
  if (invite.is_expired) return { label: 'Expired', color: 'error' }
  return { label: 'Pending', color: 'primary' }
}

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
  invites.value.filter((invite) => {
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

const loadInvites = async () => {
  try {
    loading.value = true
    error.value = null
    invites.value = await inviteService.getInvites()
  } catch (err) {
    error.value = 'Failed to load invites. Please try again later.'
    console.error('Error loading invites:', err)
  } finally {
    loading.value = false
  }
}

const handleCopyInviteLink = async (invite) => {
  try {
    await navigator.clipboard.writeText(`${window.location.origin}/register?token=${invite.token}`)
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
        await inviteService.deleteInvite(invite.id)
        invites.value = invites.value.filter((i) => i.id !== invite.id)
        emit('notification', { text: 'Invite deleted successfully', color: 'success' })
      } catch (err) {
        emit('notification', { text: 'Failed to delete invite. Please try again.', color: 'error' })
        throw err
      }
    },
  })
}

const handleCleanupExpiredInvites = async () => {
  cleanupLoading.value = true
  try {
    const result = await inviteService.cleanupExpiredInvites()
    await loadInvites()
    emit('notification', {
      text: `Cleaned up ${result.deleted_count || 0} expired invites`,
      color: 'success',
    })
  } catch (err) {
    emit('notification', { text: 'Failed to cleanup expired invites', color: 'error' })
    console.error('Error cleaning up expired invites:', err)
  } finally {
    cleanupLoading.value = false
  }
}

const handleInviteCreated = (invite) => {
  invites.value.unshift(invite)
  showNewInviteModal.value = false
  emit('notification', { text: 'Invite generated successfully!', color: 'success' })
}

onMounted(loadInvites)
</script>
