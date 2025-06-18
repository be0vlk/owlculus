<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Domain -->
    <v-text-field
      v-model="localParams.domain"
      label="Domain"
      placeholder="Enter target domain (e.g., example.com)"
      variant="outlined"
      density="compact"
      :rules="[domainRule]"
      @update:model-value="updateParams"
    />

    <!-- Concurrency -->
    <v-text-field
      v-model.number="localParams.concurrency"
      label="Concurrency"
      placeholder="Maximum concurrent DNS queries"
      type="number"
      variant="outlined"
      density="compact"
      min="1"
      max="200"
      @update:model-value="updateParams"
    />

    <!-- SecurityTrails Option -->
    <v-switch
      v-model="localParams.use_securitytrails"
      label="Enable SecurityTrails API"
      hint="Requires SecurityTrails API key configuration"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Case Evidence Toggle -->
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

const { domainRule } = usePluginValidation()

// Local parameter state for plugin-specific params
const localParams = reactive({
  domain: props.modelValue.domain || '',
  concurrency: props.modelValue.concurrency || 5,
  use_securitytrails: props.modelValue.use_securitytrails || false
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
    domain: newValue.domain || '',
    concurrency: newValue.concurrency || 5,
    use_securitytrails: newValue.use_securitytrails || false
  })
}, { deep: true })
</script>