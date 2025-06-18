<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

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

    <!-- Save to Case Option -->
    <CaseEvidenceToggle 
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />

  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'
import { usePluginValidation } from '@/composables/usePluginParams'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'

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

const { emailRule } = usePluginValidation()

// Local parameter state for plugin-specific params
const localParams = reactive({
  email: props.modelValue.email || '',
  timeout: props.modelValue.timeout || 10.0
})


// Emit parameter updates for plugin-specific params
const updateParams = () => {
  emit('update:modelValue', { 
    ...props.modelValue,
    ...localParams 
  })
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, {
    email: newValue.email || '',
    timeout: newValue.timeout || 10.0
  })
}, { deep: true })
</script>