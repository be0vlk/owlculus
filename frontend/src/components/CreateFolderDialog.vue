<template>
  <v-dialog v-model="dialog" max-width="500px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-folder-plus" class="mr-2"></v-icon>
        Create New Folder
      </v-card-title>
      
      <v-card-text>
        <v-form ref="form" v-model="valid" lazy-validation @submit.prevent>
          <v-text-field
            v-model="folderName"
            label="Folder Name"
            :rules="folderNameRules"
            required
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-folder"
          ></v-text-field>
          
          <v-textarea
            v-model="description"
            label="Description (Optional)"
            variant="outlined"
            density="comfortable"
            rows="2"
            prepend-inner-icon="mdi-text"
          ></v-textarea>
          
          <v-alert
            v-if="error"
            type="error"
            variant="tonal"
            class="mb-0"
          >
            {{ error }}
          </v-alert>
        </v-form>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          color="grey"
          variant="text"
          @click="cancel"
          :disabled="loading"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="createFolder"
          :loading="loading"
          :disabled="!valid || !folderName.trim()"
        >
          Create Folder
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { evidenceService } from '../services/evidence'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  caseId: {
    type: Number,
    required: true
  },
  parentFolderId: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'folderCreated'])

// Reactive data
const form = ref()
const valid = ref(false)
const loading = ref(false)
const error = ref('')
const folderName = ref('')
const description = ref('')

// Computed
const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Validation rules
const folderNameRules = [
  v => !!v || 'Folder name is required',
  v => (v && v.length >= 1) || 'Folder name must be at least 1 character',
  v => (v && v.length <= 255) || 'Folder name must be less than 255 characters',
  v => /^[a-zA-Z0-9._\s-]+$/.test(v) || 'Folder name can only contain letters, numbers, spaces, dots, underscores, and hyphens'
]

// Methods
const createFolder = async () => {
  // Trigger validation and wait for it to complete
  const isValid = await form.value.validate()
  if (!isValid.valid) {
    return
  }

  // Double check the folder name is not empty
  if (!folderName.value.trim()) {
    return
  }

  loading.value = true
  error.value = ''

  try {
    const newFolder = await evidenceService.createFolder({
      caseId: props.caseId,
      title: folderName.value.trim(),
      description: description.value.trim() || null,
      parentFolderId: props.parentFolderId || null
    })

    emit('folderCreated', newFolder)
    resetForm()
    dialog.value = false
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to create folder'
  } finally {
    loading.value = false
  }
}

const cancel = () => {
  resetForm()
  dialog.value = false
}

const resetForm = () => {
  folderName.value = ''
  description.value = ''
  error.value = ''
  if (form.value) {
    form.value.resetValidation()
  }
}

// Watch for dialog close to reset form
watch(dialog, (newVal) => {
  if (!newVal) {
    resetForm()
  }
})
</script>