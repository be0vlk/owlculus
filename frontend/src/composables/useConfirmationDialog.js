import { ref } from 'vue'

export function useConfirmationDialog() {
  // Dialog state
  const showDialog = ref(false)
  const dialogTitle = ref('')
  const dialogMessage = ref('')
  const dialogIcon = ref('mdi-alert-circle')
  const dialogIconColor = ref('error')
  const confirmButtonText = ref('Confirm')
  const confirmButtonColor = ref('error')
  const cancelButtonText = ref('Cancel')
  const loading = ref(false)
  const warningText = ref('')

  // Store the resolve/reject functions for the promise
  let resolveFunction = null
  let rejectFunction = null

  // Show confirmation dialog and return a promise
  const confirm = (options = {}) => {
    return new Promise((resolve, reject) => {
      // Store the promise functions
      resolveFunction = resolve
      rejectFunction = reject

      // Set dialog options
      dialogTitle.value = options.title || 'Confirm Action'
      dialogMessage.value = options.message || 'Are you sure you want to continue?'
      dialogIcon.value = options.icon || 'mdi-alert-circle'
      dialogIconColor.value = options.iconColor || 'error'
      confirmButtonText.value = options.confirmText || 'Confirm'
      confirmButtonColor.value = options.confirmColor || 'error'
      cancelButtonText.value = options.cancelText || 'Cancel'
      warningText.value = options.warning || ''

      // Show the dialog
      showDialog.value = true
    })
  }

  // Handle confirm action
  const handleConfirm = async () => {
    if (resolveFunction) {
      loading.value = true
      try {
        await resolveFunction(true)
      } catch (error) {
        // Handle any errors from the confirm action
        console.error('Confirmation action failed:', error)
      } finally {
        loading.value = false
        closeDialog()
      }
    }
  }

  // Handle cancel action
  const handleCancel = () => {
    if (rejectFunction) {
      rejectFunction(false)
    }
    closeDialog()
  }

  // Close the dialog and cleanup
  const closeDialog = () => {
    showDialog.value = false
    loading.value = false

    // Clear the promise functions
    resolveFunction = null
    rejectFunction = null

    // Reset to defaults
    dialogTitle.value = ''
    dialogMessage.value = ''
    dialogIcon.value = 'mdi-alert-circle'
    dialogIconColor.value = 'error'
    confirmButtonText.value = 'Confirm'
    confirmButtonColor.value = 'error'
    cancelButtonText.value = 'Cancel'
    warningText.value = ''
  }

  // Convenience methods for common dialog types
  const confirmDelete = (itemName = 'item') => {
    return confirm({
      title: 'Confirm Deletion',
      message: `Are you sure you want to delete ${itemName}?`,
      icon: 'mdi-delete-alert',
      iconColor: 'error',
      confirmText: 'Delete',
      confirmColor: 'error',
      warning: 'This action cannot be undone.',
    })
  }

  const confirmAction = (action, itemName = '') => {
    return confirm({
      title: `Confirm ${action}`,
      message: `Are you sure you want to ${action.toLowerCase()} ${itemName}?`,
      confirmText: action,
      confirmColor: 'primary',
    })
  }

  return {
    // State
    showDialog,
    dialogTitle,
    dialogMessage,
    dialogIcon,
    dialogIconColor,
    confirmButtonText,
    confirmButtonColor,
    cancelButtonText,
    loading,
    warningText,

    // Methods
    confirm,
    handleConfirm,
    handleCancel,
    closeDialog,

    // Convenience methods
    confirmDelete,
    confirmAction,
  }
}
