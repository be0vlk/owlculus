<template>
  <div>
    <v-text-field
      v-if="field.type === 'string'"
      v-model="model"
      :label="field.label"
      :rules="rules"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
    />

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

    <v-checkbox
      v-else-if="field.type === 'boolean'"
      v-model="model"
      :label="field.label"
      :hint="field.description"
      :persistent-hint="!!field.description"
      :readonly="readonly"
      density="comfortable"
    />

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
