<template>
  <v-dialog v-model="dialogVisible" max-width="600px" persistent>
    <v-card prepend-icon="mdi-briefcase-edit" title="Edit Case">
      <v-card-text>
        <!-- Error Alert -->
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>

        <v-form ref="formRef" v-model="isFormValid" @submit.prevent="handleSubmit">
          <!-- Case Details Section -->
          <v-card variant="outlined" class="mb-6">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-information</v-icon>
              Case Information
            </v-card-title>
            
            <v-card-text>
              <v-text-field
                v-model="formData.title"
                label="Case Title"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-briefcase"
                :rules="[rules.required, rules.titleLength]"
                counter="100"
                placeholder="Enter a descriptive case title"
                class="mb-4"
                :readonly="updating"
              />

              <v-select
                v-model="formData.status"
                :items="statusOptions"
                label="Case Status"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-flag"
                :rules="[rules.required]"
                :readonly="updating"
              />
            </v-card-text>
          </v-card>

          <!-- Case Metadata (Read-only info) -->
          <v-card variant="outlined" v-if="caseData.created_at">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-clock</v-icon>
              Case Timeline
            </v-card-title>
            
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <div class="mb-4">
                    <div class="text-caption text-medium-emphasis mb-1">
                      <v-icon size="16" class="me-1">mdi-calendar-plus</v-icon>
                      Created
                    </div>
                    <v-chip
                      variant="outlined"
                      size="small"
                      class="font-mono"
                    >
                      {{ formatDate(caseData.created_at) }}
                    </v-chip>
                  </div>
                </v-col>
                
                <v-col cols="12" md="6">
                  <div class="mb-4">
                    <div class="text-caption text-medium-emphasis mb-1">
                      <v-icon size="16" class="me-1">mdi-calendar-edit</v-icon>
                      Last Updated
                    </div>
                    <v-chip
                      variant="outlined"
                      size="small"
                      class="font-mono"
                    >
                      {{ formatDate(caseData.updated_at) }}
                    </v-chip>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-form>
      </v-card-text>

      <v-divider />

      <ModalActions
        submit-text="Save Changes"
        submit-icon="mdi-content-save"
        :submit-disabled="updating || !isFormValid"
        :loading="updating"
        @cancel="$emit('close')"
        @submit="handleSubmit"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import api from '../services/api'
import { formatDate } from '../composables/dateUtils'
import ModalActions from './ModalActions.vue'

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
      status: '',
      created_at: null,
      updated_at: null
    })
  }
})

const emit = defineEmits(['close', 'update'])

// Reactive variables
const formRef = ref(null)
const isFormValid = ref(false)
const updating = ref(false)
const error = ref(null)

// Status options with icons and colors
const statusOptions = [
  { 
    value: 'Open', 
    title: 'Open',
    props: {
      prependIcon: 'mdi-folder-open',
      color: 'success'
    }
  },
  { 
    value: 'Closed', 
    title: 'Closed',
    props: {
      prependIcon: 'mdi-folder',
      color: 'grey'
    }
  }
]

// Validation rules
const rules = {
  required: (value) => !!value || 'This field is required',
  titleLength: (value) => {
    if (!value) return true // handled by required rule
    return value.length <= 100 || 'Title must be 100 characters or less'
  }
}

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

// Watch for caseData changes and update form
watch(() => props.caseData, (newValue) => {
  if (newValue) {
    formData.value = {
      title: newValue.title || '',
      status: newValue.status || ''
    }
  }
}, { immediate: true })

// Reset form validation when dialog opens
watch(() => props.show, (show) => {
  if (show && formRef.value) {
    setTimeout(() => {
      formRef.value.resetValidation()
    }, 100)
  }
})

const handleSubmit = async () => {
  // Validate form before submission
  if (!formRef.value) return
  
  const { valid } = await formRef.value.validate()
  if (!valid) return
  
  updating.value = true
  error.value = null
  
  try {
    const response = await api.put(`/api/cases/${props.caseData.id}`, {
      title: formData.value.title.trim(),
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
