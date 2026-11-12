<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <template v-for="(param, paramName) in filteredParameters" :key="paramName">
      <v-switch
        v-if="param.type === 'boolean'"
        v-model="localParams[paramName]"
        :label="param.label || paramName"
        :hint="param.description"
        persistent-hint
        color="primary"
        density="compact"
        @update:model-value="updateParams"
      />

      <v-combobox
        v-else-if="param.type === 'list'"
        v-model="localParams[paramName]"
        :label="param.label || paramName"
        :hint="param.description"
        :rules="parameterRules(param, paramName)"
        multiple
        chips
        @keydown.enter.stop.prevent
        @update:model-value="updateParams"
      />

      <v-text-field
        v-else-if="param.type === 'number' || param.type === 'float'"
        v-model.number="localParams[paramName]"
        :label="param.label || paramName"
        :placeholder="param.description"
        :rules="parameterRules(param, paramName)"
        :hint="param.description"
        persistent-hint
        type="number"
        density="compact"
        @update:model-value="updateParams"
      />

      <v-text-field
        v-else
        v-model="localParams[paramName]"
        :label="param.label || paramName"
        :placeholder="param.description"
        :rules="parameterRules(param, paramName)"
        :hint="param.description"
        persistent-hint
        density="compact"
        @update:model-value="updateParams"
      />
    </template>

    <CaseEvidenceToggle
      v-if="parameters.save_to_case"
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { reactive, watch, computed, onMounted } from 'vue'
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

const pluginDescription = computed(() => {
  return props.parameters?.description || ''
})

const filteredParameters = computed(() => {
  const params = { ...props.parameters }
  delete params.save_to_case
  delete params.case_id
  delete params.description
  delete params.api_key_requirements
  return params
})

const parameterRules = (param, name) =>
  param.required
    ? [
        (value) =>
          (value !== null && value !== undefined && String(value).trim().length > 0) ||
          `${param.label || name} is required`,
      ]
    : []

const localParams = reactive({})

const initializeParams = () => {
  Object.keys(filteredParameters.value).forEach((paramName) => {
    const param = filteredParameters.value[paramName]
    if (param.type === 'list') {
      localParams[paramName] = props.modelValue[paramName] ?? param.default ?? []
    } else if (param.type === 'boolean') {
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
      localParams[paramName] = props.modelValue[paramName] ?? param.default ?? ''
    }
  })
}

onMounted(initializeParams)

const updateParams = () => {
  emit('update:modelValue', {
    ...props.modelValue,
    ...localParams,
  })
}

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
