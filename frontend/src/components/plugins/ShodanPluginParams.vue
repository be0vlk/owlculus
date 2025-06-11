<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />
    
    <!-- API Key Warning -->
    <ApiKeyWarning
      v-if="missingApiKeys.length > 0"
      :missing-providers="missingApiKeys"
    />

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
        <span class="text-caption text-medium-emphasis">{{ Math.round(localParams.limit) }} results</span>
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
    <v-switch
      v-model="caseParams.save_to_case"
      label="Save to case evidence"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateCaseParams"
    />

    <!-- Case Selection (only when save_to_case is enabled) -->
    <v-select
      v-if="caseParams.save_to_case"
      v-model="caseParams.case_id"
      label="Case to Save Evidence To"
      :items="caseItems"
      :loading="loadingCases"
      :disabled="loadingCases"
      item-title="display_name"
      item-value="id"
      persistent-hint
      variant="outlined"
      density="compact"
      @update:model-value="updateCaseParams"
    >
      <template #prepend-item>
        <v-list-item>
          <v-list-item-title class="text-caption text-medium-emphasis">
            Only cases you have access to are shown
          </v-list-item-title>
        </v-list-item>
        <v-divider />
      </template>

      <template #no-data>
        <v-list-item>
          <v-list-item-title class="text-medium-emphasis">
            No accessible cases found
          </v-list-item-title>
        </v-list-item>
      </template>
    </v-select>

  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { useCaseSelection } from '@/composables/useCaseSelection'
import { usePluginApiKeys } from '@/composables/usePluginApiKeys'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import ApiKeyWarning from './ApiKeyWarning.vue'

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

// Search type state
const searchType = ref(props.modelValue.search_type || 'general')

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

// Local parameter state for plugin-specific params
const localParams = reactive({
  query: props.modelValue.query || '',
  search_type: searchType.value,
  limit: props.modelValue.limit || 10
})

// Use case selection composable
const {
  loadingCases,
  caseParams,
  caseItems,
  updateCaseParams
} = useCaseSelection(props, emit)

// Use plugin API keys composable
const { checkPluginApiKeys, getMissingApiKeys } = usePluginApiKeys()
const missingApiKeys = ref([])

// Check API keys on mount
onMounted(async () => {
  // Check if plugin has API key requirements
  if (props.parameters.api_key_requirements && props.parameters.api_key_requirements.length > 0) {
    const plugin = {
      name: 'ShodanPlugin',
      api_key_requirements: props.parameters.api_key_requirements
    }
    await checkPluginApiKeys(plugin)
    missingApiKeys.value = getMissingApiKeys(plugin)
  }
})

// Update search type and related parameters
const updateSearchType = () => {
  localParams.search_type = searchType.value
  updateParams()
}

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
    query: newValue.query || '',
    search_type: newValue.search_type || 'general',
    limit: newValue.limit || 10
  })
  
  // Update search type
  if (newValue.search_type) {
    searchType.value = newValue.search_type
  }
}, { deep: true })
</script>