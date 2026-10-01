<template>
  <v-form :disabled="disabled" ref="formRef" @submit.prevent="emit('submit')">
    <v-row>
      <!-- Basic Information -->
      <v-col cols="12">
        <div class="text-title-large mb-4">Basic Information</div>
      </v-col>

      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.name"
          label="Template Name"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-identifier"
          :rules="nameRules"
          :disabled="isEdit"
          hint="Unique identifier (lowercase, no spaces)"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-text-field
          v-model="form.display_name"
          label="Display Name"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-tag"
          :rules="displayNameRules"
          hint="User-friendly name"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12">
        <v-textarea
          v-model="form.description"
          label="Description"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-text"
          :rules="[required('Description')]"
          rows="2"
          hint="Describe when and how to use this template"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-combobox
          v-model="form.category"
          :items="commonCategories"
          label="Category"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-folder"
          :rules="[required('Category')]"
          hint="Type to create a new category"
          persistent-hint
          required
        />
      </v-col>

      <v-col cols="12" md="6">
        <v-switch v-model="form.is_active" label="Active" color="primary" hide-details>
          <template #label>
            <span :class="form.is_active ? '' : 'text-medium-emphasis'">
              {{ form.is_active ? 'Active' : 'Inactive' }}
            </span>
          </template>
        </v-switch>
      </v-col>

      <!-- Custom Fields -->
      <v-col cols="12">
        <v-divider class="my-4" />
        <div class="d-flex flex-wrap ga-3 align-center justify-space-between mb-4">
          <div>
            <div class="text-title-large">Custom Fields</div>
            <div class="text-body-medium text-medium-emphasis">
              Define additional fields for this task template
            </div>
          </div>
          <v-btn
            color="primary"
            variant="outlined"
            size="small"
            prepend-icon="mdi-plus"
            :disabled="disabled"
            @click="addField"
          >
            Add Field
          </v-btn>
        </div>
      </v-col>

      <!-- Field List -->
      <v-col cols="12">
        <div v-if="form.definition_json.fields.length === 0" class="empty-fields text-center py-8">
          <v-icon icon="mdi-form-textbox" size="48" color="grey-lighten-1" class="mb-2" />
          <div class="text-title-large font-weight-medium mb-2">No Custom Fields</div>
          <p class="text-body-medium text-medium-emphasis">
            Add custom fields to collect additional information for this task type
          </p>
        </div>

        <v-expansion-panels v-else variant="accordion" class="mb-4">
          <v-expansion-panel v-for="(field, index) in form.definition_json.fields" :key="index">
            <v-expansion-panel-title>
              <div class="d-flex align-center flex-grow-1">
                <v-icon :icon="fieldType(field.type)?.icon || 'mdi-help-circle'" class="me-3" />
                <span v-if="field.label" class="font-weight-medium">
                  {{ field.label }}
                  <span v-if="field.name" class="text-body-small text-medium-emphasis ms-2">
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
                  {{ fieldType(field.type)?.title || field.type }}
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
                      required('Field name'),
                      (v) => FIELD_NAME.test(v) || 'Must be alphanumeric with underscores',
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
                    :rules="[required('Label')]"
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
                    :disabled="disabled"
                    @click="form.definition_json.fields.splice(index, 1)"
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
import { ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  isEdit: { type: Boolean, default: false },
  existingNames: { type: Array, default: () => [] },
})
const form = defineModel({ type: Object, required: true })
const emit = defineEmits(['submit'])
const formRef = ref(null)

const FIELD_NAME = /^[a-zA-Z0-9_]+$/
const required = (label) => (v) => !!v || `${label} is required`
const nameRules = [
  required('Template name'),
  (v) =>
    /^[a-z0-9_-]+$/.test(v) ||
    'Template name must contain only lowercase letters, numbers, underscores, and hyphens',
  (v) => !props.existingNames.includes(v) || 'Template name already exists',
]
const displayNameRules = [
  required('Display name'),
  (v) => v.length >= 3 || 'Display name must be at least 3 characters',
]

const commonCategories = [
  'Investigation',
  'Analysis',
  'Documentation',
  'Review',
  'Communication',
  'Technical',
  'Administrative',
]

const fieldTypes = [
  { value: 'string', title: 'Text', icon: 'mdi-format-text' },
  { value: 'number', title: 'Number', icon: 'mdi-numeric' },
  { value: 'date', title: 'Date', icon: 'mdi-calendar' },
  { value: 'boolean', title: 'Yes/No', icon: 'mdi-toggle-switch' },
  { value: 'text', title: 'Text Area', icon: 'mdi-text-box' },
  { value: 'select', title: 'Select', icon: 'mdi-form-select' },
]
const fieldType = (value) => fieldTypes.find((type) => type.value === value)

function addField() {
  form.value.definition_json.fields.push({
    name: '',
    label: '',
    type: 'string',
    required: false,
    description: '',
  })
}

// Collapsed panels do not render their inputs, so check custom fields directly.
async function validate() {
  const { valid } = await formRef.value.validate()
  return valid && form.value.definition_json.fields.every((f) => FIELD_NAME.test(f.name) && f.label)
}

defineExpose({ validate })
</script>

<style scoped>
.empty-fields {
  border: 1px dashed rgb(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background-color: rgb(var(--v-theme-surface));
}
</style>
