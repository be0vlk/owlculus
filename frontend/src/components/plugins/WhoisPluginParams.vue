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
import { usePluginValidation } from '@/composables/usePluginParams'
import { useCaseSelection } from '@/composables/useCaseSelection'
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

const { domainRule } = usePluginValidation()

const pluginDescription = computed(() => props.parameters?.description)

// Use case selection composable
const {
  loadingCases,
  caseParams,
  caseItems,
  updateCaseParams
} = useCaseSelection(props, emit)

// Local parameter state
const localParams = reactive({
  domain: props.modelValue.domain || '',
  timeout: props.modelValue.timeout || 30,
})

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })
</script>
