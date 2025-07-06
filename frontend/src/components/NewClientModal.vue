<template>
  <BaseClientModal
    :is-open="isOpen"
    :model-value="form"
    @update:model-value="updateForm"
    title="New Client"
    :is-submitting="isSubmitting"
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
  form.name = ''
  form.email = ''
  form.phone = ''
  form.address = ''
  emit('close')
}

const handleSubmit = async () => {
  try {
    isSubmitting.value = true
    const newClient = await clientService.createClient(form)
    emit('created', newClient)
    closeModal()
  } catch (error) {
    console.error('Error creating client:', error)
  } finally {
    isSubmitting.value = false
  }
}
</script>
