<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />
    
    <!-- API Key Warning -->
    <ApiKeyWarning
      v-if="missingApiKeys.length > 0"
      :missing-providers="missingApiKeys"
    />

    <!-- Generic parameter fields -->
    <template v-for="(param, paramName) in filteredParameters" :key="paramName">
      <!-- Boolean type - Switch -->
      <v-switch
        v-if="param.type === 'boolean'"
        v-model="localParams[paramName]"
        :label="paramName"
        :hint="param.description"
        persistent-hint
        color="primary"
        density="compact"
        @update:model-value="updateParams"
      />

      <!-- Number/Float type - Number field -->
      <v-text-field
        v-else-if="param.type === 'number' || param.type === 'float'"
        v-model.number="localParams[paramName]"
        :label="paramName"
        :placeholder="param.description"
        :hint="param.description"
        persistent-hint
        type="number"
        variant="outlined"
        density="compact"
        @update:model-value="updateParams"
      />

      <!-- String type - Text field -->
      <v-text-field
        v-else
        v-model="localParams[paramName]"
        :label="paramName"
        :placeholder="param.description"
        :hint="param.description"
        persistent-hint
        variant="outlined"
        density="compact"
        @update:model-value="updateParams"
      />
    </template>

    <!-- Save to Case Option (if available) -->
    <template v-if="parameters.save_to_case">
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
    </template>
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
  },
  pluginName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

// Plugin description from backend
const pluginDescription = computed(() => {
  return props.parameters?.description || ''
})

// Filter out special parameters (save_to_case, case_id) from the displayed parameters
const filteredParameters = computed(() => {
  const params = { ...props.parameters }
  delete params.save_to_case
  delete params.case_id
  delete params.description
  return params
})

// Local parameter state for plugin-specific params
const localParams = reactive({})

// Initialize local params
const initializeParams = () => {
  Object.keys(filteredParameters.value).forEach(paramName => {
    const param = filteredParameters.value[paramName]
    if (param.type === 'boolean') {
      localParams[paramName] = props.modelValue[paramName] !== undefined 
        ? props.modelValue[paramName] 
        : (param.default !== undefined ? param.default : false)
    } else if (param.type === 'number' || param.type === 'float') {
      localParams[paramName] = props.modelValue[paramName] !== undefined 
        ? props.modelValue[paramName] 
        : (param.default || 0)
    } else {
      localParams[paramName] = props.modelValue[paramName] || param.default || ''
    }
  })
}

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
  initializeParams()
  
  // Check if plugin has API key requirements
  if (props.parameters.api_key_requirements && props.parameters.api_key_requirements.length > 0) {
    const plugin = {
      name: props.pluginName,
      api_key_requirements: props.parameters.api_key_requirements
    }
    await checkPluginApiKeys(plugin)
    missingApiKeys.value = getMissingApiKeys(plugin)
  }
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
  Object.keys(filteredParameters.value).forEach(paramName => {
    if (newValue[paramName] !== undefined) {
      localParams[paramName] = newValue[paramName]
    }
  })
}, { deep: true })
</script>