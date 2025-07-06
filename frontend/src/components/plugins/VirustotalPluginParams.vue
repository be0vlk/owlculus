<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- API Key Warning -->
    <ApiKeyWarning v-if="missingApiKeys.length > 0" :missing-providers="missingApiKeys" />

    <!-- Target Input -->
    <v-text-field
      v-model="localParams.target"
      :label="targetLabel"
      :placeholder="targetPlaceholder"
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
      @update:model-value="updateAnalysisType"
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
import { computed } from 'vue'
import { usePluginParamsAdvanced } from '@/composables/usePluginParams'
import { usePluginApiKeys } from '@/composables/usePluginApiKeys'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import ApiKeyWarning from './ApiKeyWarning.vue'
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
const { pluginDescription, localParams, updateParams, missingApiKeys } = usePluginParamsAdvanced(
  props,
  emit,
  {
    parameterDefaults: {
      target: '',
      analysis_type: 'auto',
      include_details: true,
      timeout: 30.0,
    },
    apiKeyRequirements: props.parameters.api_key_requirements,
    onApiKeyCheck: async (requirements) => {
      const { checkPluginApiKeys, getMissingApiKeys } = usePluginApiKeys()
      const plugin = {
        name: 'VirusTotalPlugin',
        api_key_requirements: requirements,
      }
      await checkPluginApiKeys(plugin)
      return {
        missing: getMissingApiKeys(plugin),
      }
    },
  },
)

// Analysis type options
const analysisTypes = [
  { title: 'Auto-detect', value: 'auto' },
  { title: 'File Hash', value: 'file' },
  { title: 'URL', value: 'url' },
  { title: 'Domain', value: 'domain' },
  { title: 'IP Address', value: 'ip' },
]

// Dynamic labels and hints based on analysis type
const targetLabel = computed(() => {
  switch (localParams.analysis_type) {
    case 'file':
      return 'File Hash'
    case 'url':
      return 'URL'
    case 'domain':
      return 'Domain Name'
    case 'ip':
      return 'IP Address'
    default:
      return 'Target'
  }
})

const targetPlaceholder = computed(() => {
  switch (localParams.analysis_type) {
    case 'file':
      return 'Enter MD5, SHA1, or SHA256 hash'
    case 'url':
      return 'Enter URL (e.g., https://example.com/path)'
    case 'domain':
      return 'Enter domain name (e.g., example.com)'
    case 'ip':
      return 'Enter IP address (e.g., 8.8.8.8)'
    default:
      return 'Enter file hash, URL, domain, or IP address'
  }
})

computed(() => {
  switch (localParams.analysis_type) {
    case 'file':
      return 'Analyze file by its hash value'
    case 'url':
      return 'Check URL for malicious content'
    case 'domain':
      return 'Analyze domain reputation and history'
    case 'ip':
      return 'Check IP address reputation and associated threats'
    default:
      return 'Automatically detects target type (hash, URL, domain, or IP)'
  }
})

// Update analysis type
const updateAnalysisType = () => {
  updateParams()
}
</script>
