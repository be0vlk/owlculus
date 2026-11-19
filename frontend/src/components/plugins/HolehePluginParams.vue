<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <v-text-field
      v-model="localParams.email"
      label="Email Address"
      placeholder="Enter email address to check for account registrations"
      density="compact"
      type="email"
      :rules="[emailRule]"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout"
      placeholder="Request timeout per platform in seconds"
      type="number"
      density="compact"
      min="1"
      max="60"
      @update:model-value="updateParams"
    />

    <CaseEvidenceToggle
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { usePluginParamsAdvanced } from '@/composables/usePluginParams'
import { emailRule } from '@/composables/entityValidation'
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

const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    email: '',
    timeout: 10.0,
  },
})
</script>
