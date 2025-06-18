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
import { reactive, watch, computed } from 'vue'
import { usePluginValidation } from '@/composables/usePluginParams'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'

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

const { domainRule } = usePluginValidation()

const pluginDescription = computed(() => props.parameters?.description)


// Local parameter state
const localParams = reactive({
  domain: props.modelValue.domain || '',
  timeout: props.modelValue.timeout || 30,
})

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { 
    ...props.modelValue,
    ...localParams 
  })
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })
</script>
