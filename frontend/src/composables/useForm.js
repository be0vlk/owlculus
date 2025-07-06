// composables/useForm.js
import { ref, reactive } from 'vue'

export function useForm(initialData, submitCallback) {
  const formData = reactive({ ...initialData })
  const error = ref('')
  const creating = ref(false)

  const resetForm = () => {
    Object.assign(formData, initialData)
    error.value = ''
  }

  const handleSubmit = async () => {
    try {
      creating.value = true
      error.value = ''
      await submitCallback(formData)
      resetForm()
    } catch (err) {
      error.value = err.response?.data?.message || err.message || 'An error occurred.'
    } finally {
      creating.value = false
    }
  }

  return { formData, error, creating, handleSubmit, resetForm }
}
