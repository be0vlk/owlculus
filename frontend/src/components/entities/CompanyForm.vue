<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-domain</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-text-field
        :model-value="modelValue.name"
        @update:model-value="updateField('name', $event)"
        label="Company Name"
        variant="outlined"
        density="comfortable"
        prepend-inner-icon="mdi-domain"
        required
        placeholder="Enter company name"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { entityFormProps, entityFormEmits, useEntityFormField } from '@/composables/useEntityForm'

const props = defineProps(entityFormProps)
const emit = defineEmits(entityFormEmits)

const { updateField } = useEntityFormField(props, emit)
</script>
