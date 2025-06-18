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
import { useCaseSelection } from '@/composables/useCaseSelection'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({
      save_to_case: false,
      case_id: null
    })
  }
})

const emit = defineEmits(['update:modelValue'])

// Use case selection composable
const {
  loadingCases,
  caseParams,
  caseItems,
  updateCaseParams
} = useCaseSelection(props, emit)
</script>