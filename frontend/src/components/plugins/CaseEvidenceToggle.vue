<template>
  <div class="d-flex flex-column ga-3">
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
    <CaseSelector
      v-if="caseParams.save_to_case"
      v-model="caseParams.case_id"
      label="Case to Save Evidence To"
      @update:model-value="updateCaseParams"
    />
  </div>
</template>

<script setup>
import { useCaseSelection } from '@/composables/useCaseSelection'
import CaseSelector from './CaseSelector.vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({
      save_to_case: false,
      case_id: null,
    }),
  },
})

const emit = defineEmits(['update:modelValue'])

// Use case selection composable
const { caseParams, updateCaseParams } = useCaseSelection(props, emit)
</script>
