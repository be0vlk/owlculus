<template>
  <div>
    <!-- String field (text input) -->
    <v-text-field
      v-if="field.type === 'string'"
      v-model="model"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
    />

    <!-- Number field -->
    <v-text-field
      v-else-if="field.type === 'number'"
      v-model.number="model"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      type="number"
    />

    <!-- Date field -->
    <v-text-field
      v-else-if="field.type === 'date'"
      v-model="model"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      type="date"
    />

    <!-- Boolean field (checkbox) -->
    <v-checkbox
      v-else-if="field.type === 'boolean'"
      v-model="model"
      :label="field.label"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      density="comfortable"
    />

    <!-- Text area field -->
    <v-textarea
      v-else-if="field.type === 'text'"
      v-model="model"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      rows="3"
    />

    <!-- Select field -->
    <v-select
      v-else-if="field.type === 'select'"
      v-model="model"
      :items="field.options || []"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
    />

    <!-- Fallback for unknown field type -->
    <v-alert v-else type="warning" variant="tonal" density="compact">
      Unknown field type: {{ field.type }}
    </v-alert>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  field: {
    type: Object,
    required: true,
  },
  readonly: {
    type: Boolean,
    default: false,
  },
})
const model = defineModel({ default: null })

const rules = computed(() =>
  props.field.required ? [(v) => !!v || `${props.field.label} is required`] : [],
)
</script>
