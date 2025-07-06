<template>
  <v-form ref="form" @submit.prevent="handleSubmit">
    <v-row>
      <!-- Basic Information -->
      <v-col cols="12">
        <div class="text-h6 mb-4">Basic Information</div>
      </v-col>

      <v-col cols="12" md="6">
        <v-text-field
          v-model="localForm.name"
          label="Template Name"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-identifier"
          :rules="[validateTemplateName]"
          :disabled="isEdit"
          hint="Unique identifier (lowercase, no spaces)"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-text-field
          v-model="localForm.display_name"
          label="Display Name"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-tag"
          :rules="[validateDisplayName]"
          hint="User-friendly name"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12">
        <v-textarea
          v-model="localForm.description"
          label="Description"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-text"
          :rules="[validateDescription]"
          rows="2"
          hint="Describe when and how to use this template"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-combobox
          v-model="localForm.category"
          :items="commonCategories"
          label="Category"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-folder"
          :rules="[validateCategory]"
          hint="Type to create a new category"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-switch v-model="localForm.is_active" label="Active" color="primary" hide-details>
          <template #label>
            <span :class="localForm.is_active ? '' : 'text-medium-emphasis'">
              {{ localForm.is_active ? 'Active' : 'Inactive' }}
            </span>
          </template>
        </v-switch>
      </v-col>

      <!-- Custom Fields -->
      <v-col cols="12">
        <v-divider class="my-4" />
        <div class="d-flex align-center justify-space-between mb-4">
          <div>
            <div class="text-h6">Custom Fields</div>
            <div class="text-body-2 text-medium-emphasis">
              Define additional fields for this task template
            </div>
          </div>
          <v-btn
            color="primary"
            variant="outlined"
            size="small"
            prepend-icon="mdi-plus"
            @click="addField"
          >
            Add Field
          </v-btn>
        </div>
      </v-col>

      <!-- Field List -->
      <v-col cols="12">
        <div
          v-if="localForm.definition_json.fields.length === 0"
          class="empty-fields text-center py-8"
        >
          <v-icon icon="mdi-form-textbox" size="48" color="grey-lighten-1" class="mb-2" />
          <div class="text-h6 font-weight-medium mb-2">No Custom Fields</div>
          <p class="text-body-2 text-medium-emphasis">
            Add custom fields to collect additional information for this task type
          </p>
        </div>

        <v-expansion-panels v-else variant="accordion" class="mb-4">
          <v-expansion-panel
            v-for="(field, index) in localForm.definition_json.fields"
            :key="index"
          >
            <v-expansion-panel-title>
              <div class="d-flex align-center flex-grow-1">
                <v-icon :icon="getFieldIcon(field.type)" class="me-3" />
                <span v-if="field.label" class="font-weight-medium">
                  {{ field.label }}
                  <span v-if="field.name" class="text-caption text-medium-emphasis ms-2">
                    ({{ field.name }})
                  </span>
                </span>
                <span v-else class="text-medium-emphasis"> New Field {{ index + 1 }} </span>
                <v-spacer />
                <v-chip
                  v-if="field.required"
                  size="small"
                  color="error"
                  variant="tonal"
                  class="me-2"
                >
                  Required
                </v-chip>
                <v-chip size="small" variant="tonal">
                  {{ getFieldTypeLabel(field.type) }}
                </v-chip>
              </div>
            </v-expansion-panel-title>

            <v-expansion-panel-text>
              <v-row class="mt-2">
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="field.name"
                    label="Field Name"
                    variant="outlined"
                    density="compact"
                    :rules="[
                      (v) => !!v || 'Field name is required',
                      (v) => /^[a-zA-Z0-9_]+$/.test(v) || 'Must be alphanumeric with underscores',
                    ]"
                    hint="Internal field identifier"
                    persistent-hint
                    required
                  />
                </v-col>

                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="field.label"
                    label="Display Label"
                    variant="outlined"
                    density="compact"
                    :rules="[(v) => !!v || 'Label is required']"
                    hint="User-friendly field name"
                    persistent-hint
                    required
                  />
                </v-col>

                <v-col cols="12" md="6">
                  <v-select
                    v-model="field.type"
                    :items="fieldTypes"
                    label="Field Type"
                    variant="outlined"
                    density="compact"
                  />
                </v-col>

                <v-col cols="12" md="6">
                  <v-switch
                    v-model="field.required"
                    label="Required Field"
                    color="primary"
                    density="compact"
                    hide-details
                  />
                </v-col>

                <v-col cols="12">
                  <v-textarea
                    v-model="field.description"
                    label="Field Description (Optional)"
                    variant="outlined"
                    density="compact"
                    rows="2"
                    hint="Help text for users"
                    persistent-hint
                  />
                </v-col>

                <v-col cols="12">
                  <v-btn
                    color="error"
                    variant="text"
                    size="small"
                    prepend-icon="mdi-delete"
                    @click="removeField(index)"
                  >
                    Remove Field
                  </v-btn>
                </v-col>
              </v-row>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-col>
    </v-row>
  </v-form>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  isEdit: {
    type: Boolean,
    default: false,
  },
  validateTemplateName: {
    type: Function,
    required: true,
  },
  validateDisplayName: {
    type: Function,
    required: true,
  },
  validateDescription: {
    type: Function,
    required: true,
  },
  validateCategory: {
    type: Function,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue', 'submit'])

// Local copy of form data
const localForm = ref(JSON.parse(JSON.stringify(props.modelValue)))

// Common categories
const commonCategories = [
  'Investigation',
  'Analysis',
  'Documentation',
  'Review',
  'Communication',
  'Technical',
  'Administrative',
]

// Field types
const fieldTypes = [
  { title: 'Text', value: 'string' },
  { title: 'Number', value: 'number' },
  { title: 'Date', value: 'date' },
  { title: 'Boolean', value: 'boolean' },
  { title: 'Text Area', value: 'text' },
  { title: 'Select', value: 'select' },
]

// Field type icons
const fieldTypeIcons = {
  string: 'mdi-format-text',
  number: 'mdi-numeric',
  date: 'mdi-calendar',
  boolean: 'mdi-toggle-switch',
  text: 'mdi-text-box',
  select: 'mdi-form-select',
}

// Field type labels
const fieldTypeLabels = {
  string: 'Text',
  number: 'Number',
  date: 'Date',
  boolean: 'Yes/No',
  text: 'Text Area',
  select: 'Select',
}

// Methods
const getFieldIcon = (type) => {
  return fieldTypeIcons[type] || 'mdi-help-circle'
}

const getFieldTypeLabel = (type) => {
  return fieldTypeLabels[type] || type
}

const addField = () => {
  if (!localForm.value.definition_json.fields) {
    localForm.value.definition_json.fields = []
  }
  localForm.value.definition_json.fields.push({
    name: '',
    label: '',
    type: 'string',
    required: false,
    description: '',
  })
}

const removeField = (index) => {
  localForm.value.definition_json.fields.splice(index, 1)
}

const handleSubmit = () => {
  emit('submit')
}

// Form ref
const form = ref(null)

// Expose validate method
const validate = async () => {
  const { valid } = await form.value.validate()

  // Also validate fields
  if (valid && localForm.value.definition_json.fields.length > 0) {
    const fieldsValid = localForm.value.definition_json.fields.every((field) => {
      return field.name && /^[a-zA-Z0-9_]+$/.test(field.name) && field.label
    })
    return fieldsValid
  }

  return valid
}

// Watch for prop changes
watch(
  () => props.modelValue,
  (newValue) => {
    // Only update if the values are actually different to prevent loops
    if (JSON.stringify(newValue) !== JSON.stringify(localForm.value)) {
      localForm.value = JSON.parse(JSON.stringify(newValue))
    }
  },
  { deep: true },
)

// Emit changes with debouncing to prevent infinite loops
let emitTimeout = null
watch(
  localForm,
  (newValue) => {
    clearTimeout(emitTimeout)
    emitTimeout = setTimeout(() => {
      emit('update:modelValue', JSON.parse(JSON.stringify(newValue)))
    }, 100)
  },
  { deep: true },
)

// Expose methods to parent
defineExpose({
  validate,
})
</script>

<style scoped>
.empty-fields {
  border: 1px dashed rgb(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background-color: rgb(var(--v-theme-surface));
}
</style>
