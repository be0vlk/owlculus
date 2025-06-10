<template>
  <v-dialog
    v-model="dialogVisible"
    max-width="500px"
    persistent
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-folder-plus</v-icon>
        New Case
      </v-card-title>
      
      <v-card-text>
        <v-form ref="form" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="formData.title"
            label="Title"
            variant="outlined"
            density="comfortable"
            :rules="[v => !!v || 'Title is required']"
            required
            class="mb-4"
          />

          <v-select
            v-model="formData.client_id"
            :items="clientOptions"
            item-title="name"
            item-value="id"
            label="Client"
            variant="outlined"
            density="comfortable"
            :rules="[v => !!v || 'Client is required']"
            required
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="closeModal"
          :disabled="isSubmitting"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          :loading="isSubmitting"
          @click="handleSubmit"
        >
          {{ isSubmitting ? 'Creating...' : 'Create Case' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { clientService } from '../services/client'
import { caseService } from '../services/case'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  }
})

const dialogVisible = computed({
  get: () => props.isOpen,
  set: (value) => {
    if (!value) {
      closeModal()
    }
  }
})

const emit = defineEmits(['close', 'created'])

const authStore = useAuthStore()
const clients = ref([])
const isSubmitting = ref(false)
const form = ref(null)
const formData = reactive({
  title: '',
  client_id: '',
  status: 'Open'
})

const clientOptions = computed(() => clients.value)

const loadClients = async () => {
  // Only load clients if user is admin
  if (!authStore.requiresAdmin()) {
    return;
  }
  
  try {
    clients.value = await clientService.getClients()
  } catch (error) {
    console.error('Error loading clients:', error)
  }
}

// Auto-select client when only one exists
watch(clients, (newClients) => {
  if (newClients && newClients.length === 1 && !formData.client_id) {
    formData.client_id = newClients[0].id
  }
})

const closeModal = () => {
  // Reset form
  formData.title = ''
  formData.client_id = ''
  formData.status = 'Open'
  if (form.value) {
    form.value.reset()
  }
  emit('close')
}

const handleSubmit = async () => {
  const { valid } = await form.value.validate()
  if (!valid) return

  try {
    isSubmitting.value = true
    const newCase = await caseService.createCase(formData)
    emit('created', newCase)
    closeModal()
  } catch (error) {
    console.error('Error creating case:', error)
    // TODO: Add proper error handling UI
  } finally {
    isSubmitting.value = false
  }
}

// Load clients when modal opens
watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    loadClients()
  }
})

onMounted(loadClients)
</script>