<template>
  <v-card variant="outlined">
    <v-card-title class="text-body-large">
      <v-icon start>mdi-account</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            :model-value="modelValue.first_name"
            autofocus
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
        <v-col cols="12" md="6"
          ><v-text-field
            :model-value="modelValue.email"
            @update:model-value="updateField('email', $event)"
            label="Email"
            variant="outlined"
        /></v-col>
        <v-col cols="12" md="6"
          ><v-text-field
            :model-value="modelValue.phone"
            @update:model-value="updateField('phone', $event)"
            label="Phone"
            variant="outlined"
        /></v-col>
        <v-col cols="12" md="6"
          ><v-text-field
            :model-value="modelValue.employer"
            @update:model-value="updateField('employer', $event)"
            label="Employer"
            variant="outlined"
        /></v-col>
        <v-col cols="12"
          ><v-text-field
            :model-value="modelValue.social_media?.other"
            @update:model-value="
              updateField('social_media', { ...modelValue.social_media, other: $event })
            "
            label="Profile URL"
            variant="outlined"
        /></v-col>
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
