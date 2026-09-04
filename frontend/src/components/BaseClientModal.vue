<template>
  <v-dialog
    :model-value="dialogVisible"
    :aria-label="title"
    max-width="500px"
    persistent
    @update:model-value="(val) => !val && $emit('close')"
  >
    <v-card>
      <v-card-title>
        <span class="text-headline-small">{{ title }}</span>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
        <v-form :id="formId" ref="formRef" :disabled="isSubmitting" @submit.prevent="submit">
          <v-text-field
            :model-value="modelValue.name"
            @update:model-value="updateField('name', $event)"
            label="Name"
            required
            :rules="[(v) => !!v?.trim() || 'Name is required']"
            autofocus
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            :model-value="modelValue.email"
            @update:model-value="updateField('email', $event)"
            label="Email"
            :rules="[(v) => !v || /.+@.+\..+/.test(v) || 'Email must be valid']"
            type="email"
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            :model-value="modelValue.phone"
            @update:model-value="updateField('phone', $event)"
            label="Phone"
            type="tel"
            variant="outlined"
            density="comfortable"
          />

          <v-textarea
            :model-value="modelValue.address"
            @update:model-value="updateField('address', $event)"
            label="Address"
            rows="3"
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn :disabled="isSubmitting" variant="text" @click="$emit('close')"> Cancel </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          type="submit"
          :form="formId"
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
import { computed, ref, useId } from 'vue'

const props = defineProps({
  error: { type: String, default: '' },
  isOpen: {
    type: Boolean,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  modelValue: {
    type: Object,
    required: true,
  },
  isSubmitting: {
    type: Boolean,
    default: false,
  },
  submitButtonText: {
    type: String,
    required: true,
  },
})

const formId = useId()
const formRef = ref(null)
const submit = async () => {
  if (props.isSubmitting) return
  const { valid } = await formRef.value.validate()
  if (valid && !props.isSubmitting) emit('submit')
}

const emit = defineEmits(['close', 'submit', 'update:modelValue'])

const dialogVisible = computed(() => props.isOpen)

const updateField = (field, value) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value,
  })
}
</script>
