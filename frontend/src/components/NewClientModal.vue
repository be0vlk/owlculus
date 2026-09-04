<template>
  <BaseClientModal
    :is-open="isOpen"
    :model-value="form"
    @update:model-value="updateForm"
    title="New Client"
    :is-submitting="isSubmitting"
    :error="error"
    :submit-button-text="isSubmitting ? 'Creating...' : 'Create Client'"
    @close="closeModal"
    @submit="handleSubmit"
  />
</template>

<script setup>
import { ref, reactive } from 'vue'
import { clientService } from '../services/client'
import BaseClientModal from './BaseClientModal.vue'

defineProps({
  isOpen: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['close', 'created'])

const isSubmitting = ref(false)
const error = ref('')
const form = reactive({
  name: '',
  email: '',
  phone: '',
  address: '',
})

const updateForm = (newForm) => {
  Object.assign(form, newForm)
}

const closeModal = () => {
  error.value = ''
  form.name = ''
  form.email = ''
  form.phone = ''
  form.address = ''
  emit('close')
}

const handleSubmit = async () => {
  if (isSubmitting.value) return
  error.value = ''
  try {
    isSubmitting.value = true
    const newClient = await clientService.createClient({ ...form, email: form.email || null })
    emit('created', newClient)
    closeModal()
  } catch (err) {
    error.value = 'Failed to create client. Please try again.'
    console.error('Error creating client:', err)
  } finally {
    isSubmitting.value = false
  }
}
</script>
