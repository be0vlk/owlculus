<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start :icon="isEdit ? 'mdi-pencil' : 'mdi-plus'" />
      {{ isEdit ? 'Edit Task' : 'Create Task' }}
    </v-card-title>
    <v-divider />
    <v-card-text class="pa-4">
      <v-form ref="form" v-model="valid">
        <v-select
          v-model="formData.case_id"
          :disabled="isEdit || !!caseId"
          :items="cases"
          :rules="[(v) => !!v || 'Case is required']"
          item-title="title"
          item-value="id"
          label="Case"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-text-field
          v-model="formData.title"
          :rules="[(v) => !!v || 'Title is required']"
          label="Title"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-textarea
          v-model="formData.description"
          :rules="[(v) => !!v || 'Description is required']"
          label="Description"
          rows="3"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-select
          v-if="!isEdit"
          v-model="formData.template_id"
          :items="templates"
          clearable
          item-title="display_name"
          item-value="id"
          label="Template (Optional)"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-select 
          v-model="formData.priority" 
          :items="priorityOptions" 
          label="Priority"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-select
          v-model="formData.assigned_to_id"
          :items="filteredUsers"
          clearable
          item-title="username"
          item-value="id"
          label="Assign To"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <v-text-field 
          v-model="formData.due_date" 
          clearable 
          label="Due Date" 
          type="date"
          variant="outlined"
          density="comfortable"
          class="mb-4"
        />

        <!-- Custom Fields -->
        <div v-if="customFields.length > 0" class="mt-4">
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
        :disabled="!valid" 
        :loading="loading" 
        color="primary" 
        variant="flat"
        @click="save"
      >
        {{ isEdit ? 'Update' : 'Create' }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { caseService } from '@/services/case'
import { TASK_PRIORITY, TASK_PRIORITY_LABELS } from '@/constants/tasks'
import CustomFieldInput from './CustomFieldInput.vue'

const props = defineProps({
  task: {
    type: Object,
    default: null,
  },
  caseId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['save', 'cancel'])

const taskStore = useTaskStore()

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const cases = ref([])

const isEdit = computed(() => !!props.task)

const formData = ref({
  case_id: props.caseId || props.task?.case_id || null,
  title: props.task?.title || '',
  description: props.task?.description || '',
  template_id: null,
  priority: props.task?.priority || TASK_PRIORITY.MEDIUM,
  assigned_to_id: props.task?.assigned_to_id || null,
  due_date: props.task?.due_date ? props.task.due_date.split('T')[0] : null,
  custom_fields: props.task?.custom_fields || {},
})

const templates = computed(() => taskStore.templates)
const customFields = ref([])

const priorityOptions = computed(() =>
  Object.entries(TASK_PRIORITY_LABELS).map(([value, title]) => ({ title, value })),
)

const filteredUsers = computed(() => {
  if (!formData.value.case_id) return []

  const selectedCase = cases.value.find((c) => c.id === formData.value.case_id)
  return selectedCase?.users || []
})

// Watch for template selection changes
watch(
  () => formData.value.template_id,
  (newTemplateId) => {
    if (newTemplateId && !isEdit.value) {
      // Find the selected template
      const selectedTemplate = templates.value.find((t) => t.id === newTemplateId)
      if (selectedTemplate) {
        // Auto-fill title and description from template
        formData.value.title = selectedTemplate.display_name
        formData.value.description = selectedTemplate.description

        // Set custom fields from template
        if (selectedTemplate.definition_json?.fields) {
          customFields.value = selectedTemplate.definition_json.fields
          // Initialize custom field values
          const customFieldValues = {}
          selectedTemplate.definition_json.fields.forEach((field) => {
            customFieldValues[field.name] =
              formData.value.custom_fields[field.name] || (field.type === 'boolean' ? false : '')
          })
          formData.value.custom_fields = customFieldValues
        } else {
          customFields.value = []
        }
      }
    } else if (!newTemplateId) {
      // Clear custom fields when no template is selected
      customFields.value = []
      formData.value.custom_fields = {}
    }
  },
)

async function save() {
  // Check if form is valid using v-model binding
  if (!valid.value) return

  loading.value = true
  try {
    // Format date if present
    const data = { ...formData.value }
    if (data.due_date) {
      data.due_date = new Date(data.due_date).toISOString()
    }

    emit('save', data)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // Load required data
  try {
    const [casesData] = await Promise.all([caseService.getCases(), taskStore.loadTemplates()])
    cases.value = casesData
    // Templates are already stored in the taskStore

    // If editing a task with a template, load custom fields
    if (isEdit.value && props.task?.template_id) {
      const template = templates.value.find((t) => t.id === props.task.template_id)
      if (template?.definition_json?.fields) {
        customFields.value = template.definition_json.fields
      }
    }
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>
