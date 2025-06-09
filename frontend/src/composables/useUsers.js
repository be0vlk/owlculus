import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import { formatDate } from '@/composables/dateUtils'

export function useUsers() {
  const authStore = useAuthStore()
  
  // State
  const users = ref([])
  const loading = ref(true)
  const error = ref(null)
  const searchQuery = ref('')
  const sortKey = ref('username')
  const sortOrder = ref('asc')
  
  // Modal state
  const showNewUserModal = ref(false)
  const editingUser = ref(null)
  const showPasswordResetModal = ref(false)
  const selectedUserForPasswordReset = ref(null)
  
  // Vuetify table headers
  const vuetifyHeaders = [
    { title: 'Username', key: 'username', sortable: true },
    { title: 'Email', key: 'email', sortable: true },
    { title: 'Role', key: 'role', sortable: true },
    { title: 'Created', key: 'created_at', sortable: true },
    { title: 'Actions', key: 'actions', sortable: false }
  ]

  // Computed
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

  // Permission checking functions
  const canDeleteUser = (targetUser) => {
    const currentUser = authStore.user
    if (!currentUser) return false
    
    // Cannot delete yourself
    if (currentUser.id === targetUser.id) return false
    
    // Cannot delete superadmin users
    if (targetUser.is_superadmin) return false
    
    // Only superadmin can delete admin users
    if (targetUser.role === 'Admin' && !currentUser.is_superadmin) return false
    
    // Regular admins can delete non-admin users
    return true
  }

  const canResetPassword = (targetUser) => {
    const currentUser = authStore.user
    if (!currentUser) return false
    
    // Only superadmin can reset superadmin passwords
    if (targetUser.is_superadmin && !currentUser.is_superadmin) return false
    
    // All admins can reset non-superadmin passwords
    return true
  }

  const canEditUser = (targetUser) => {
    const currentUser = authStore.user
    if (!currentUser) return false
    
    // Only superadmin can edit superadmin users
    if (targetUser.is_superadmin && !currentUser.is_superadmin) return false
    
    // All admins can edit non-superadmin users
    return true
  }

  // Helper functions
  const getRoleColor = () => {
    return 'grey-darken-1'
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

  // CRUD operations
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

  const deleteUser = async (userId) => {
    try {
      await userService.deleteUser(userId)
      users.value = users.value.filter(u => u.id !== userId)
      return true
    } catch (err) {
      console.error('Error deleting user:', err)
      throw err
    }
  }

  // Modal management
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
      const index = users.value.findIndex(u => u.id === user.id)
      if (index !== -1) {
        users.value[index] = user
      }
    } else {
      users.value.push(user)
    }
    closeUserModal()
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
  }

  return {
    // State
    users,
    loading,
    error,
    searchQuery,
    sortKey,
    sortOrder,
    
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
  }
}