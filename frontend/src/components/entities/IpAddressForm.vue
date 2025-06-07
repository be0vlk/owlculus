<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-ip</v-icon>
      Details
    </v-card-title>

    <v-card-text>
      <v-text-field
        :model-value="modelValue.ip_address"
        @update:model-value="updateField('ip_address', $event)"
        label="IP Address"
        variant="outlined"
        density="comfortable"
        prepend-inner-icon="mdi-ip"
        placeholder="192.168.1.1"
        required
        class="mb-4"
        :rules="[ipRule]"
      />

      <v-textarea
        :model-value="modelValue.description"
        @update:model-value="updateField('description', $event)"
        label="Description (Optional)"
        variant="outlined"
        density="comfortable"
        rows="3"
        placeholder="Add any notes or context about this IP address"
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

const ipRule = (value) => {
  if (!value) return 'IP address is required'
  const ipPattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
  return ipPattern.test(value) || 'Please enter a valid IP address'
}
</script>