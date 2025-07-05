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
import {
  usePluginValidation,
  usePluginParamsAdvanced,
  pluginParamConfigs,
} from '@/composables/usePluginParams'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'

const props = defineProps({
  parameters: {
    type: Object,
    required: true,
  },
  modelValue: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

// Use advanced plugin params composable with email configuration
const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    ...pluginParamConfigs.email(),
    timeout: 10.0,
  },
})

const { emailRule } = usePluginValidation()
</script>
