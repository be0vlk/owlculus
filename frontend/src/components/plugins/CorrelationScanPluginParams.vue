<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Case to Scan Selection -->
    <CaseSelector
      v-model="localParams.case_id"
      label="Case to Scan"
      @update:model-value="updateParams"
    />

    <!-- Case Evidence Toggle -->
    <CaseEvidenceToggle
      :model-value="evidenceToggleParams"
      @update:model-value="updateEvidenceParams"
    />

  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePluginParamsAdvanced } from '@/composables/usePluginParams'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'
import CaseSelector from './CaseSelector.vue'

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

// Use advanced plugin params composable with case_id configuration
const {
  pluginDescription,
  localParams,
  updateParams
} = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    case_id: null
  }
})

// Evidence toggle parameters (separate from case to scan)
const evidenceToggleParams = computed(() => ({
  save_to_case: props.modelValue.save_to_case || false,
  case_id: props.modelValue.case_id || null
}))

const updateEvidenceParams = (evidenceParams) => {
  emit('update:modelValue', {
    ...props.modelValue,
    save_to_case: evidenceParams.save_to_case,
    case_id: evidenceParams.case_id || localParams.case_id
  })
}
</script>

<style scoped>
ul {
  list-style-type: disc;
}

li {
  margin-bottom: 4px;
}
</style>
