<template>
  <v-col :cols="field.gridCols === 2 ? 12 : 6">
    <div v-if="field.hasSource" class="d-flex flex-column gap-2">
      <v-textarea
        v-if="field.type === 'textarea'"
        :model-value="fieldValue"
        @update:model-value="$emit('update:field', $event)"
        :label="field.label"
        variant="outlined"
        density="comfortable"
        rows="3"
        auto-grow
        clearable
      />
      <v-text-field
        v-else
        :model-value="fieldValue"
        @update:model-value="$emit('update:field', $event)"
        :label="field.label"
        :type="field.type"
        variant="outlined"
        density="comfortable"
        clearable
        :prepend-inner-icon="getFieldIcon(field.type)"
      />
      <v-text-field
        :model-value="sourceValue"
        @update:model-value="$emit('update:source', $event)"
        :label="`Source for ${field.label}`"
        variant="outlined"
        density="comfortable"
        clearable
        prepend-inner-icon="mdi-source-branch"
        placeholder="URL, description, or reference where this was found"
        class="source-field"
      />
    </div>
    <div v-else>
      <v-textarea
        v-if="field.type === 'textarea'"
        :model-value="fieldValue"
        @update:model-value="$emit('update:field', $event)"
        :label="field.label"
        variant="outlined"
        density="comfortable"
        rows="3"
        auto-grow
        clearable
      />
      <v-text-field
        v-else
        :model-value="fieldValue"
        @update:model-value="$emit('update:field', $event)"
        :label="field.label"
        :type="field.type"
        variant="outlined"
        density="comfortable"
        clearable
        :prepend-inner-icon="getFieldIcon(field.type)"
      />
    </div>
  </v-col>
</template>

<script setup>
import { useEntityIcons } from '../../composables/useEntityIcons.js'

const props = defineProps({
  field: { type: Object, required: true },
  fieldValue: { type: [String, Number], default: '' },
  sourceValue: { type: String, default: '' },
  entity: { type: Object, required: true }
})

defineEmits(['update:field', 'update:source'])

const { getFieldIcon } = useEntityIcons(props.entity)
</script>

<style scoped>
@import '../../styles/entity-editor.css';
</style>