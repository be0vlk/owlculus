<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-account</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="modelValue.first_name"
            @update:model-value="updateField('first_name', $event)"
            label="First Name"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-account-outline"
          />
        </v-col>

        <v-col cols="12" md="6">
          <v-text-field
            :model-value="modelValue.last_name"
            @update:model-value="updateField('last_name', $event)"
            label="Last Name"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-account-outline"
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