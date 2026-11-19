import { ref } from 'vue'

const DEFAULTS = {
  title: 'Confirm Action',
  message: 'Are you sure you want to continue?',
  icon: 'mdi-alert-circle',
  iconColor: 'error',
  confirmText: 'Confirm',
  confirmColor: 'error',
  cancelText: 'Cancel',
  warning: '',
}

export function useConfirmationDialog() {
  const showDialog = ref(false)
  const opts = ref(DEFAULTS)
  let settle = null

  // Resolves with true on confirm, rejects with false on cancel.
  const confirm = (options = {}) =>
    new Promise((resolve, reject) => {
      settle = (confirmed) => (confirmed ? resolve(true) : reject(false))
      opts.value = { ...DEFAULTS, ...options }
      showDialog.value = true
    })

  const close = (confirmed) => {
    settle?.(confirmed)
    settle = null
    showDialog.value = false
  }

  const confirmDelete = (itemName = 'item') =>
    confirm({
      title: 'Confirm Deletion',
      message: `Are you sure you want to delete ${itemName}?`,
      icon: 'mdi-delete-alert',
      confirmText: 'Delete',
      warning: 'This action cannot be undone.',
    })

  return {
    showDialog,
    opts,
    confirm,
    confirmDelete,
    handleConfirm: () => close(true),
    handleCancel: () => close(false),
  }
}
