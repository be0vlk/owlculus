<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">New Client</span>
      </v-card-title>
      <v-card-text>
        <v-form @submit.prevent="handleSubmit">
          <v-text-field
            v-model="form.name"
            label="Name"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            v-model="form.email"
            label="Email"
            type="email"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            v-model="form.phone"
            label="Phone"
            type="tel"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-textarea
            v-model="form.address"
            label="Address"
            rows="3"
            required
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="closeModal"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleSubmit"
          :disabled="isSubmitting"
          :loading="isSubmitting"
        >
          {{ isSubmitting ? 'Creating...' : 'Create Client' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
// Vuetify components are auto-imported
import { clientService } from '../services/client'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['close', 'created'])

const dialogVisible = computed({
  get: () => props.isOpen,
  set: (value) => {
    if (!value) {
      closeModal()
    }
  }
})

const isSubmitting = ref(false)
const form = reactive({
  name: '',
  email: '',
  phone: '',
  address: ''
})

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