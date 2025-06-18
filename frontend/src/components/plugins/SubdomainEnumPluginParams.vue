<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Domain -->
    <v-text-field
      v-model="localParams.domain"
      label="Domain"
      placeholder="Enter target domain (e.g., example.com)"
      variant="outlined"
      density="compact"
      :rules="[domainRule]"
      @update:model-value="updateParams"
    />

    <!-- Concurrency -->
    <v-text-field
      v-model.number="localParams.concurrency"
      label="Concurrency"
      placeholder="Maximum concurrent DNS queries"
      type="number"
      variant="outlined"
      density="compact"
      min="1"
      max="200"
      @update:model-value="updateParams"
    />

    <!-- SecurityTrails Option -->
    <v-switch
      v-model="localParams.use_securitytrails"
      label="Enable SecurityTrails API"
      hint="Requires SecurityTrails API key configuration"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateParams"
    />

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
import { reactive, watch, computed } from 'vue'
import { useCaseSelection } from '@/composables/useCaseSelection'
import { usePluginValidation } from '@/composables/usePluginParams'
import PluginDescriptionCard from './PluginDescriptionCard.vue'

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

const { domainRule } = usePluginValidation()

// Local parameter state for plugin-specific params
const localParams = reactive({
  domain: props.modelValue.domain || '',
  concurrency: props.modelValue.concurrency || 5,
  use_securitytrails: props.modelValue.use_securitytrails || false
})

// Use case selection composable
const {
  loadingCases,
  caseParams,
  caseItems,
  updateCaseParams
} = useCaseSelection(props, emit)

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
    domain: newValue.domain || '',
    concurrency: newValue.concurrency || 5,
    use_securitytrails: newValue.use_securitytrails || false
  })
}, { deep: true })
</script>