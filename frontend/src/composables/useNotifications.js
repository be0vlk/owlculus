import { ref } from 'vue'

export function useNotifications() {
  const snackbar = ref({
    show: false,
    text: '',
    color: 'success',
    timeout: 4000,
  })

  const showNotification = (text, color = 'success', timeout = 4000) => {
    snackbar.value.text = text
    snackbar.value.color = color
    snackbar.value.timeout = timeout
    snackbar.value.show = true
  }

  const showSuccess = (text, timeout = 4000) => {
    showNotification(text, 'success', timeout)
  }

  const showError = (text, timeout = 6000) => {
    showNotification(text, 'error', timeout)
  }

  const closeNotification = () => {
    snackbar.value.show = false
  }

  return {
    snackbar,

    showNotification,
    showSuccess,
    showError,
    closeNotification,
  }
}
