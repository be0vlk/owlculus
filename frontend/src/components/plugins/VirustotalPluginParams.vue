<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Target Input -->
    <v-text-field
      v-model="localParams.target"
      :label="targetText[localParams.analysis_type].label"
      :placeholder="targetText[localParams.analysis_type].placeholder"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Analysis Type Selection -->
    <v-select
      v-model="localParams.analysis_type"
      label="Analysis Type"
      :items="analysisTypes"
      item-title="title"
      item-value="value"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Include Extended Details -->
    <v-switch
      v-model="localParams.include_details"
      label="Include Extended Details"
      color="primary"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Timeout -->
    <v-text-field
      v-model.number="localParams.timeout"
      label="API Timeout (seconds)"
      placeholder="30"
      type="number"
      variant="outlined"
      density="compact"
      min="5"
      max="120"
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
import { usePluginParamsAdvanced } from '@/composables/usePluginParams'
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

// Use advanced plugin params composable
const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    target: '',
    analysis_type: 'auto',
    include_details: true,
    timeout: 30.0,
  },
})

// Analysis type options
const analysisTypes = [
  { title: 'Auto-detect', value: 'auto' },
  { title: 'File Hash', value: 'file' },
  { title: 'URL', value: 'url' },
  { title: 'Domain', value: 'domain' },
  { title: 'IP Address', value: 'ip' },
]

const targetText = {
  auto: { label: 'Target', placeholder: 'Enter file hash, URL, domain, or IP address' },
  file: { label: 'File Hash', placeholder: 'Enter MD5, SHA1, or SHA256 hash' },
  url: { label: 'URL', placeholder: 'Enter URL (e.g., https://example.com/path)' },
  domain: { label: 'Domain Name', placeholder: 'Enter domain name (e.g., example.com)' },
  ip: { label: 'IP Address', placeholder: 'Enter IP address (e.g., 8.8.8.8)' },
}
</script>
