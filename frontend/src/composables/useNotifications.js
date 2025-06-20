import { ref } from 'vue'

export function useNotifications () {
  // Snackbar state
  const snackbar = ref({
    show: false,
    text: '',
    color: 'success',
    timeout: 4000
  })

  // Helper function to show notifications
  const showNotification = (text, color = 'success', timeout = 4000) => {
    snackbar.value.text = text
    snackbar.value.color = color
    snackbar.value.timeout = timeout
    snackbar.value.show = true
  }

  // Convenience methods for common notification types
  const showSuccess = (text, timeout = 4000) => {
    showNotification(text, 'success', timeout)
  }

  const showError = (text, timeout = 6000) => {
    showNotification(text, 'error', timeout)
  }

  const showWarning = (text, timeout = 5000) => {
    showNotification(text, 'warning', timeout)
  }

  const showInfo = (text, timeout = 4000) => {
    showNotification(text, 'info', timeout)
  }

  // Close the snackbar
  const closeNotification = () => {
    snackbar.value.show = false
  }

  return {
    // State
    snackbar,

    // Methods
    showNotification,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    closeNotification
  }
}
