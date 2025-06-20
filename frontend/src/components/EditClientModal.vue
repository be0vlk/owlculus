<template>
  <BaseClientModal
    :is-open="isOpen"
    :model-value="form"
    @update:model-value="updateForm"
    title="Edit Client"
    :is-submitting="isSubmitting"
    :submit-button-text="isSubmitting ? 'Updating...' : 'Update Client'"
    @close="closeModal"
    @submit="handleSubmit"
  />
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { clientService } from '../services/client'
import BaseClientModal from './BaseClientModal.vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  client: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'updated'])

const isSubmitting = ref(false)
const form = reactive({
  name: '',
  email: '',
  phone: '',
  address: ''
})

// Watch for client prop changes to populate form
watch(() => props.client, (newClient) => {
  if (newClient) {
    form.name = newClient.name || ''
    form.email = newClient.email || ''
    form.phone = newClient.phone || ''
    form.address = newClient.address || ''
  }
}, { immediate: true })

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
  if (!props.client?.id) return

  try {
    isSubmitting.value = true
    const updatedClient = await clientService.updateClient(props.client.id, form)
    emit('updated', updatedClient)
    closeModal()
  } catch (error) {
    console.error('Error updating client:', error)
  } finally {
    isSubmitting.value = false
  }
}
</script>