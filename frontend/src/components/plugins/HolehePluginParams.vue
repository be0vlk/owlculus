<template>
  <div class="d-flex flex-column ga-3">
    <!-- About Plugin Information Card -->
    <v-card
      v-if="pluginDescription"
      color="blue-lighten-5"
      elevation="0"
      rounded="lg"
      class="pa-3"
    >
      <div class="d-flex align-center ga-2 mb-2">
        <v-icon color="blue">mdi-information</v-icon>
        <span class="text-subtitle2 font-weight-medium">About</span>
      </div>
      <p class="text-body-2 mb-0">
        {{ pluginDescription }}
      </p>
    </v-card>

    <!-- Email -->
    <v-text-field
      v-model="localParams.email"
      label="Email Address"
      placeholder="Enter email address to check for account registrations"
      variant="outlined"
      density="compact"
      type="email"
      :rules="[emailRule]"
      @update:model-value="updateParams"
    />

    <!-- Timeout -->
    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout"
      placeholder="Request timeout per platform in seconds"
      type="number"
      variant="outlined"
      density="compact"
      min="1"
      max="60"
      @update:model-value="updateParams"
    />
  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'

const props = defineProps({
  parameters: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

// Plugin description from backend
const pluginDescription = computed(() => {
  return props.parameters?.description || ''
})

// Email validation rule
const emailRule = (value) => {
  if (!value) return 'Email address is required'
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return pattern.test(value) || 'Please enter a valid email address'
}

// Local parameter state
const localParams = reactive({
  email: props.modelValue.email || '',
  timeout: props.modelValue.timeout || 10.0
})

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })
</script>