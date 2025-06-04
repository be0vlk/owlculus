<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">Edit Case</span>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form @submit.prevent="handleSubmit">
      <div>
        <label for="title" class="block text-sm font-medium mb-1">Title</label>
        <v-text-field
          id="title"
          v-model="formData.title"
          required
          variant="outlined"
          density="comfortable"
        />
      </div>

      <div>
        <label for="status" class="block text-sm font-medium mb-1">Status</label>
        <v-select
          v-model="formData.status"
          :items="[
            { value: 'Open', title: 'Open' },
            { value: 'Closed', title: 'Closed' }
          ]"
          item-title="title"
          item-value="value"
          required
          variant="outlined"
          density="comfortable"
        />
      </div>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleSubmit"
          :disabled="updating"
          :loading="updating"
        >
          {{ updating ? 'Saving...' : 'Save Changes' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import api from '../services/api'
// Vuetify components are auto-imported

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  caseData: {
    type: Object,
    required: true,
    default: () => ({
      title: '',
      status: ''
    })
  }
})

const emit = defineEmits(['close', 'update'])

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

const formData = ref({
  title: '',
  status: ''
})
const updating = ref(false)
const error = ref(null)

// Use watch instead of onMounted to handle updates to caseData
watch(() => props.caseData, (newValue) => {
  if (newValue) {
    formData.value = {
      title: newValue.title || '',
      status: newValue.status || ''
    }
  }
}, { immediate: true })

const handleSubmit = async () => {
  if (!formData.value) return
  
  updating.value = true
  error.value = null
  
  try {
    const response = await api.put(`/api/cases/${props.caseData.id}`, {
      title: formData.value.title,
      status: formData.value.status
    })
    emit('update', response.data)
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.message || 'Failed to update case'
  } finally {
    updating.value = false
  }
}
</script>
