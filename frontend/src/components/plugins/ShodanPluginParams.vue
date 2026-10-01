<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Search Type Selection -->
    <v-radio-group v-model="searchType" inline density="compact">
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
      :label="queryText[searchType].label"
      :placeholder="queryText[searchType].placeholder"
      :hint="queryText[searchType].hint"
      density="compact"
      persistent-hint
      @update:model-value="updateParams"
    />

    <!-- Result Limit -->
    <div>
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="text-subtitle2">Result Limit</span>
        <span class="text-body-small text-medium-emphasis"
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
          <span class="text-body-small">1</span>
        </template>
        <template #append>
          <span class="text-body-small">100</span>
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

// Use advanced plugin params composable with search configuration
const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    query: '',
    search_type: 'general',
    limit: 10,
  },
})

// Search type state (computed from localParams)
const searchType = computed({
  get: () => localParams.search_type,
  set: (value) => {
    localParams.search_type = value
    updateParams()
  },
})

const queryText = {
  general: {
    label: 'Search Query',
    placeholder: 'Enter search query (e.g., apache, port:22, org:"Google")',
    hint: 'Use Shodan query syntax (apache, port:80, country:US, etc.)',
  },
  ip: {
    label: 'IP Address',
    placeholder: 'Enter IP address (e.g., 8.8.8.8)',
    hint: 'Search for specific IP address information',
  },
  hostname: {
    label: 'Hostname',
    placeholder: 'Enter hostname (e.g., google.com)',
    hint: 'Search for hosts with specific hostname',
  },
}
</script>
