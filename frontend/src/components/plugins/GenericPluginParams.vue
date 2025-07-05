<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- API Key Warning -->
    <ApiKeyWarning v-if="missingApiKeys.length > 0" :missing-providers="missingApiKeys" />

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
    <CaseEvidenceToggle
      v-if="parameters.save_to_case"
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
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
  pluginName: {
    type: String,
    default: '',
  },
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
  Object.keys(filteredParameters.value).forEach((paramName) => {
    const param = filteredParameters.value[paramName]
    if (param.type === 'boolean') {
      localParams[paramName] =
        props.modelValue[paramName] !== undefined
          ? props.modelValue[paramName]
          : param.default !== undefined
            ? param.default
            : false
    } else if (param.type === 'number' || param.type === 'float') {
      localParams[paramName] =
        props.modelValue[paramName] !== undefined ? props.modelValue[paramName] : param.default || 0
    } else {
      localParams[paramName] = props.modelValue[paramName] || param.default || ''
    }
  })
}

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
      api_key_requirements: props.parameters.api_key_requirements,
    }
    await checkPluginApiKeys(plugin)
    missingApiKeys.value = getMissingApiKeys(plugin)
  }
})

// Emit parameter updates for plugin-specific params
const updateParams = () => {
  emit('update:modelValue', {
    ...props.modelValue,
    ...localParams,
  })
}

// Watch for external changes to modelValue
watch(
  () => props.modelValue,
  (newValue) => {
    Object.keys(filteredParameters.value).forEach((paramName) => {
      if (newValue[paramName] !== undefined) {
        localParams[paramName] = newValue[paramName]
      }
    })
  },
  { deep: true },
)
</script>
