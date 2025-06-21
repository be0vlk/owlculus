import { ref, computed } from 'vue'
import { inviteService } from '@/services/invite'
import { formatDate } from '@/composables/dateUtils'

export function useInvites() {
  // State
  const invites = ref([])
  const loading = ref(true)
  const error = ref(null)
  const inviteSearchQuery = ref('')
  const cleanupLoading = ref(false)

  // Modal state
  const showNewInviteModal = ref(false)

  // Invite table headers
  const inviteHeaders = [
    { title: 'Role', key: 'role', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Created', key: 'created_at', sortable: true },
    { title: 'Expires', key: 'expires_at', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false },
  ]

  // Computed
  const sortedAndFilteredInvites = computed(() => {
    let filteredInvites = invites.value

    // Apply search filter
    if (inviteSearchQuery.value) {
      const query = inviteSearchQuery.value.toLowerCase()
      filteredInvites = invites.value.filter((invite) =>
        (invite.role || '').toLowerCase().includes(query),
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

  // Helper functions
  const getRoleColor = () => {
    return 'grey-darken-1'
  }

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

  // Empty state functions
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
      return "Try adjusting your search terms to find the invite you're looking for."
    } else if ((invites.value || []).length === 0) {
      return 'Generate your first invite to allow new users to register.'
    } else {
      return 'Try adjusting your search to see more invites.'
    }
  }

  const shouldShowCreateInviteButton = () => {
    return (invites.value || []).length === 0 && !inviteSearchQuery.value
  }

  // CRUD operations
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

  const deleteInvite = async (invite) => {
    try {
      await inviteService.deleteInvite(invite.id)
      invites.value = invites.value.filter((i) => i.id !== invite.id)
      return true
    } catch (err) {
      console.error('Error deleting invite:', err)
      throw err
    }
  }

  const cleanupExpiredInvites = async () => {
    try {
      cleanupLoading.value = true
      const result = await inviteService.cleanupExpiredInvites()
      await loadInvites() // Refresh the list
      return result
    } catch (err) {
      console.error('Error cleaning up expired invites:', err)
      throw err
    } finally {
      cleanupLoading.value = false
    }
  }

  const copyInviteLink = async (invite) => {
    try {
      const baseUrl = window.location.origin
      const inviteLink = `${baseUrl}/register?token=${invite.token}`
      await navigator.clipboard.writeText(inviteLink)
      return true
    } catch (err) {
      console.error('Error copying invite link:', err)
      throw err
    }
  }

  // Modal management
  const closeInviteModal = () => {
    showNewInviteModal.value = false
  }

  const handleInviteCreated = (invite) => {
    invites.value.unshift(invite)
    closeInviteModal()
  }

  return {
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
  }
}
