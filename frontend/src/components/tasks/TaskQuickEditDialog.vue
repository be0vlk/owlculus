<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start icon="mdi-pencil-box-outline" />
      Quick Edit Task
    </v-card-title>
    <v-card-subtitle>{{ task.title }}</v-card-subtitle>
    <v-divider />
    <v-card-text class="pa-4">
      <v-form ref="form" :id="formId" v-model="valid" :disabled="loading" @submit.prevent="save">
        <!-- Status Update -->
        <v-select
          v-model="formData.status"
          :items="TASK_STATUS_OPTIONS"
          label="Status"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <!-- Due Date (only for admin/lead) -->
        <v-text-field
          v-if="canEditDueDate"
          v-model="formData.due_date"
          label="Due Date"
          type="date"
          variant="outlined"
          density="comfortable"
          clearable
          class="mb-4"
        />

        <!-- Custom Fields -->
        <div v-if="customFields.length > 0">
          <v-divider class="mb-4" />
          <div class="text-title-small text-medium-emphasis mb-3">Additional Fields</div>
          <CustomFieldInput
            v-for="field in customFields"
            :key="field.name"
            v-model="formData.custom_fields[field.name]"
            :field="field"
            class="mb-2"
          />
        </div>
      </v-form>
    </v-card-text>
    <v-divider />
    <v-card-actions class="pa-4">
      <v-spacer />
      <v-btn :disabled="loading" variant="text" @click="$emit('cancel')">Cancel</v-btn>
      <v-btn
        :disabled="!valid || !hasChanges"
        :loading="loading"
        color="primary"
        variant="flat"
        type="submit"
        :form="formId"
      >
        Save Changes
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { useId, ref, computed, watch } from 'vue'
import { TASK_STATUS_OPTIONS } from '@/constants/tasks'
import CustomFieldInput from './CustomFieldInput.vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  saving: { type: Boolean, default: false },
  task: {
    type: Object,
    required: true,
  },
  customFields: {
    type: Array,
    default: () => [],
  },
  isUserCaseLead: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['save', 'cancel'])

const authStore = useAuthStore()
const formId = useId()
const form = ref(null)
const valid = ref(false)
const validating = ref(false)
const loading = computed(() => validating.value || props.saving)

// Check if user can edit due date (admin or lead)
const canEditDueDate = computed(() => {
  return authStore.user?.role === 'Admin' || props.isUserCaseLead
})

// Initialize form data with current task values
const formData = ref({
  status: props.task.status,
  due_date: props.task.due_date ? props.task.due_date.split('T')[0] : null,
  custom_fields: { ...props.task.custom_fields },
})

// Track original values to detect changes
const originalData = {
  status: props.task.status,
  due_date: props.task.due_date ? props.task.due_date.split('T')[0] : null,
  custom_fields: { ...props.task.custom_fields },
}

// Only changed fields are sent.
const updates = computed(() => {
  const result = {}
  if (formData.value.status !== originalData.status) result.status = formData.value.status
  if (canEditDueDate.value && formData.value.due_date !== originalData.due_date) {
    result.due_date = formData.value.due_date
      ? new Date(formData.value.due_date).toISOString()
      : null
  }
  const changedFields = props.customFields.filter((field) => {
    const current = formData.value.custom_fields[field.name]
    const original = originalData.custom_fields[field.name]
    return field.type === 'boolean' ? !!current !== !!original : current !== original
  })
  if (changedFields.length) {
    result.custom_fields = { ...props.task.custom_fields }
    changedFields.forEach((field) => {
      result.custom_fields[field.name] = formData.value.custom_fields[field.name]
    })
  }
  return result
})
const hasChanges = computed(() => Object.keys(updates.value).length > 0)

async function save() {
  if (loading.value) return
  validating.value = true
  try {
    const result = await form.value.validate()
    if (!result.valid || !hasChanges.value || props.saving) return
    emit('save', updates.value)
  } finally {
    validating.value = false
  }
}

// Reset form data when task prop changes
watch(
  () => props.task,
  (newTask) => {
    formData.value = {
      status: newTask.status,
      due_date: newTask.due_date ? newTask.due_date.split('T')[0] : null,
      custom_fields: { ...newTask.custom_fields },
    }
  },
  { deep: true },
)
</script>
