<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-web</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-text-field
        :model-value="modelValue.domain"
        @update:model-value="updateField('domain', $event)"
        label="Domain Name"
        variant="outlined"
        density="comfortable"
        prepend-inner-icon="mdi-web"
        placeholder="example.com"
        required
        class="mb-4"
        :rules="[domainRule]"
      />

      <v-textarea
        :model-value="modelValue.description"
        @update:model-value="updateField('description', $event)"
        label="Description (Optional)"
        variant="outlined"
        density="comfortable"
        rows="3"
        placeholder="Add any notes or context about this domain"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const updateField = (field, value) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value
  })
}

const domainRule = (value) => {
  if (!value) return 'Domain is required'
  const domainPattern = /^[a-zA-Z0-9][a-zA-Z0-9-_]*\.{1}[a-zA-Z]{2,}$/
  return domainPattern.test(value) || 'Please enter a valid domain name'
}
</script>