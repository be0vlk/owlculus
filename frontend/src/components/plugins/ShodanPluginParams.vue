<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- API Key Warning -->
    <ApiKeyWarning v-if="missingApiKeys.length > 0" :missing-providers="missingApiKeys" />

    <!-- Search Type Selection -->
    <v-radio-group
      v-model="searchType"
      inline
      density="compact"
      @update:model-value="updateSearchType"
    >
      <template #label>
        <span class="text-subtitle2">Search Type</span>
      </template>
      <v-radio label="General Query" value="general" />
      <v-radio label="IP Address" value="ip" />
      <v-radio label="Hostname" value="hostname" />
    </v-radio-group>

    <!-- Search Query Input -->
    <v-text-field
      v-model="localParams.query"
      :label="queryLabel"
      :placeholder="queryPlaceholder"
      :hint="queryHint"
      variant="outlined"
      density="compact"
      persistent-hint
      @update:model-value="updateParams"
    />

    <!-- Result Limit -->
    <div>
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="text-subtitle2">Result Limit</span>
        <span class="text-caption text-medium-emphasis"
          >{{ Math.round(localParams.limit) }} results</span
        >
      </div>
      <v-slider
        v-model="localParams.limit"
        min="1"
        max="100"
        step="1"
        color="primary"
        density="compact"
        @update:model-value="updateParams"
      >
        <template #prepend>
          <span class="text-caption">1</span>
        </template>
        <template #append>
          <span class="text-caption">100</span>
        </template>
      </v-slider>
    </div>

    <!-- Save to Case Option -->
    <CaseEvidenceToggle
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePluginParamsAdvanced, pluginParamConfigs } from '@/composables/usePluginParams'
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

// Use advanced plugin params composable with search configuration
const { pluginDescription, localParams, updateParams, missingApiKeys } = usePluginParamsAdvanced(
  props,
  emit,
  {
    parameterDefaults: {
      ...pluginParamConfigs.searchQuery(),
      search_type: 'general',
      limit: 10,
    },
    apiKeyRequirements: props.parameters.api_key_requirements,
    onApiKeyCheck: async (requirements) => {
      const { checkPluginApiKeys, getMissingApiKeys } = usePluginApiKeys()
      const plugin = {
        name: 'ShodanPlugin',
        api_key_requirements: requirements,
      }
      await checkPluginApiKeys(plugin)
      return {
        missing: getMissingApiKeys(plugin),
      }
    },
  },
)

// Search type state (computed from localParams)
const searchType = computed({
  get: () => localParams.search_type,
  set: (value) => {
    localParams.search_type = value
    updateParams()
  },
})

// Dynamic labels and hints based on search type
const queryLabel = computed(() => {
  switch (searchType.value) {
    case 'ip':
      return 'IP Address'
    case 'hostname':
      return 'Hostname'
    default:
      return 'Search Query'
  }
})

const queryPlaceholder = computed(() => {
  switch (searchType.value) {
    case 'ip':
      return 'Enter IP address (e.g., 8.8.8.8)'
    case 'hostname':
      return 'Enter hostname (e.g., google.com)'
    default:
      return 'Enter search query (e.g., apache, port:22, org:"Google")'
  }
})

const queryHint = computed(() => {
  switch (searchType.value) {
    case 'ip':
      return 'Search for specific IP address information'
    case 'hostname':
      return 'Search for hosts with specific hostname'
    default:
      return 'Use Shodan query syntax (apache, port:80, country:US, etc.)'
  }
})

// Update search type
const updateSearchType = () => {
  updateParams()
}
</script>
