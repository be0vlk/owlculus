<template>
  <div>
    <!-- String field (text input) -->
    <v-text-field
      v-if="field.type === 'string'"
      v-model="localValue"
      :label="field.label"
      :rules="getRules()"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      variant="outlined"
      density="comfortable"
    />

    <!-- Number field -->
    <v-text-field
      v-else-if="field.type === 'number'"
      v-model.number="localValue"
      :label="field.label"
      :rules="getRules()"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      type="number"
      variant="outlined"
      density="comfortable"
    />

    <!-- Date field -->
    <v-text-field
      v-else-if="field.type === 'date'"
      v-model="localValue"
      :label="field.label"
      :rules="getRules()"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      type="date"
      variant="outlined"
      density="comfortable"
    />

    <!-- Boolean field (checkbox) -->
    <v-checkbox
      v-else-if="field.type === 'boolean'"
      v-model="localValue"
      :label="field.label"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      density="comfortable"
    />

    <!-- Text area field -->
    <v-textarea
      v-else-if="field.type === 'text'"
      v-model="localValue"
      :label="field.label"
      :rules="getRules()"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      variant="outlined"
      density="comfortable"
      rows="3"
    />

    <!-- Select field -->
    <v-select
      v-else-if="field.type === 'select'"
      v-model="localValue"
      :items="field.options || []"
      :label="field.label"
      :rules="getRules()"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      variant="outlined"
      density="comfortable"
    />

    <!-- Fallback for unknown field type -->
    <v-alert v-else type="warning" variant="tonal" density="compact">
      Unknown field type: {{ field.type }}
    </v-alert>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  field: {
    type: Object,
    required: true,
  },
  modelValue: {
    default: null,
  },
  readonly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

// Local value that syncs with v-model
const localValue = ref(props.modelValue)

// Watch for external changes
watch(
  () => props.modelValue,
  (newValue) => {
    localValue.value = newValue
  },
)

// Emit changes
watch(localValue, (newValue) => {
  emit('update:modelValue', newValue)
})

// Get validation rules for the field
function getRules() {
  const rules = []

  if (props.field.required) {
    rules.push((v) => {
      if (props.field.type === 'boolean') {
        return true // Boolean fields don't need required validation
      }
      return !!v || `${props.field.label} is required`
    })
  }

  return rules
}
</script>
