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
import { usePluginValidation, usePluginParamsAdvanced, pluginParamConfigs } from '@/composables/usePluginParams'
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

// Use advanced plugin params composable with domain/concurrency/securitytrails configuration
const {
  pluginDescription,
  localParams,
  updateParams
} = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: pluginParamConfigs.domainWithSecurityTrails()
})

const { domainRule } = usePluginValidation()
</script>