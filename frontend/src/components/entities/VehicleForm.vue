<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-car</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="modelValue.make"
            @update:model-value="updateField('make', $event)"
            label="Make"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-factory"
            placeholder="Toyota"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="modelValue.model"
            @update:model-value="updateField('model', $event)"
            label="Model"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-car-info"
            placeholder="Camry"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { entityFormProps, entityFormEmits, useEntityFormField } from '@/composables/useEntityForm'

const props = defineProps(entityFormProps)
const emit = defineEmits(entityFormEmits)

const { updateField } = useEntityFormField(props, emit)
</script>
