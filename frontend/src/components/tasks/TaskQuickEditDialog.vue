<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start icon="mdi-pencil-box-outline" />
      Quick Edit Task
    </v-card-title>
    <v-card-subtitle>{{ task.title }}</v-card-subtitle>
    <v-divider />
    <v-card-text class="pa-4">
      <v-form ref="form" v-model="valid">
        <!-- Status Update -->
        <v-select
          v-model="formData.status"
          :items="statusOptions"
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
          <div class="text-subtitle-2 text-medium-emphasis mb-3">Additional Fields</div>
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
      <v-btn variant="text" @click="$emit('cancel')">Cancel</v-btn>
      <v-btn
        :disabled="!valid || !hasChanges"
        :loading="loading"
        color="primary"
        variant="flat"
        @click="save"
      >
        Save Changes
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { TASK_STATUS_LABELS } from '@/constants/tasks'
import CustomFieldInput from './CustomFieldInput.vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
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
const form = ref(null)
const valid = ref(false)
const loading = ref(false)

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

const statusOptions = computed(() =>
  Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({ title, value })),
)

// Check if any changes have been made
const hasChanges = computed(() => {
  // Check status change
  if (formData.value.status !== originalData.status) return true

  // Check due date change (only if user can edit it)
  if (canEditDueDate.value && formData.value.due_date !== originalData.due_date) return true

  // Check custom fields changes
  if (props.customFields.length > 0) {
    for (const field of props.customFields) {
      const currentValue = formData.value.custom_fields[field.name]
      const originalValue = originalData.custom_fields[field.name]

      // Handle different types of comparisons
      if (field.type === 'boolean') {
        if (!!currentValue !== !!originalValue) return true
      } else if (currentValue !== originalValue) {
        return true
      }
    }
  }

  return false
})

async function save() {
  if (!valid.value || !hasChanges.value) return

  loading.value = true
  try {
    // Only send changed fields
    const updates = {}

    if (formData.value.status !== originalData.status) {
      updates.status = formData.value.status
    }

    // Check for due date changes (only if user can edit it)
    if (canEditDueDate.value && formData.value.due_date !== originalData.due_date) {
      // Convert to ISO format if date is provided, otherwise set to null
      updates.due_date = formData.value.due_date
        ? new Date(formData.value.due_date).toISOString()
        : null
    }

    // Check for custom field changes
    const customFieldChanges = {}
    let hasCustomFieldChanges = false

    if (props.customFields.length > 0) {
      for (const field of props.customFields) {
        const currentValue = formData.value.custom_fields[field.name]
        const originalValue = originalData.custom_fields[field.name]

        if (
          field.type === 'boolean'
            ? !!currentValue !== !!originalValue
            : currentValue !== originalValue
        ) {
          customFieldChanges[field.name] = currentValue
          hasCustomFieldChanges = true
        }
      }
    }

    if (hasCustomFieldChanges) {
      // Merge changed custom fields with existing ones
      updates.custom_fields = {
        ...props.task.custom_fields,
        ...customFieldChanges,
      }
    }

    emit('save', updates)
  } finally {
    loading.value = false
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
