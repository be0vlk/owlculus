<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <v-text-field
      v-model="localParams.domain"
      label="Domain Name"
      placeholder="example.com"
      variant="outlined"
      density="compact"
      :rules="[domainRule]"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout (seconds)"
      placeholder="30"
      variant="outlined"
      density="compact"
      type="number"
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

// Use advanced plugin params composable with domain configuration
const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    ...pluginParamConfigs.domain(),
    timeout: 30,
  },
})

const { domainRule } = usePluginValidation()
</script>
