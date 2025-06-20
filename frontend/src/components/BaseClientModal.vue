<template>
  <v-dialog :model-value="dialogVisible" max-width="500px" persistent @update:model-value="val => !val && $emit('close')">
    <v-card>
      <v-card-title>
        <span class="text-h5">{{ title }}</span>
      </v-card-title>
      <v-card-text>
        <v-form @submit.prevent="$emit('submit')">
          <v-text-field
            :model-value="modelValue.name"
            @update:model-value="updateField('name', $event)"
            label="Name"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            :model-value="modelValue.email"
            @update:model-value="updateField('email', $event)"
            label="Email"
            type="email"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            :model-value="modelValue.phone"
            @update:model-value="updateField('phone', $event)"
            label="Phone"
            type="tel"
            required
            variant="outlined"
            density="comfortable"
          />

          <v-textarea
            :model-value="modelValue.address"
            @update:model-value="updateField('address', $event)"
            label="Address"
            rows="3"
            required
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="$emit('submit')"
          :disabled="isSubmitting"
          :loading="isSubmitting"
        >
          {{ submitButtonText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  modelValue: {
    type: Object,
    required: true
  },
  isSubmitting: {
    type: Boolean,
    default: false
  },
  submitButtonText: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close', 'submit', 'update:modelValue'])

const dialogVisible = computed(() => props.isOpen)

const updateField = (field, value) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value
  })
}
</script>